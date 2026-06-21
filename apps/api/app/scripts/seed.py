"""Seed script — populates categories and initial sources.

Run with:
    python -m app.scripts.seed
"""

import asyncio
import uuid
from datetime import datetime

from sqlalchemy import select

import hashlib

from app.core.database import async_session_factory
from app.models.models import Category, Source
from app.models.observability_models import PromptVersionModel

CATEGORIES = [
    {"slug": "politics", "name": "Politics", "icon": "landmark"},
    {"slug": "technology", "name": "Technology", "icon": "cpu"},
    {"slug": "business", "name": "Business", "icon": "briefcase"},
    {"slug": "sports", "name": "Sports", "icon": "trophy"},
    {"slug": "health", "name": "Health", "icon": "heart-pulse"},
    {"slug": "science", "name": "Science", "icon": "flask-conical"},
    {"slug": "entertainment", "name": "Entertainment", "icon": "clapperboard"},
    {"slug": "lifestyle", "name": "Lifestyle", "icon": "sparkles"},
    {"slug": "travel", "name": "Travel", "icon": "plane"},
    {"slug": "education", "name": "Education", "icon": "graduation-cap"},
    {"slug": "weather", "name": "Weather", "icon": "cloud-sun"},
    {"slug": "world", "name": "World", "icon": "globe"},
]

PROMPT_TEMPLATES = [
    {
        "stage": "event_extraction",
        "system_prompt": None,
        "user_prompt_template": (
            "You are a structured event extraction engine for news articles.\n"
            "Extract the PRIMARY EVENT described in the article.\n\n"
            "CRITICAL RULES:\n"
            "1. event_time is WHEN THE EVENT HAPPENED, NOT when the article was published.\n"
            "   The article was published at: {published_at}. Do NOT use this as event_time.\n"
            "   If the article says 'yesterday', 'last week', 'on Monday', compute the actual date.\n"
            "   If the event time cannot be determined from the text, set event_time to null.\n"
            "2. actors = WHO performed the action (people, governments, companies, organizations)\n"
            "3. targets = WHO/WHAT was affected (victims, objects, countries affected)\n"
            "4. objects = KEY THINGS involved (weapons, documents, bills, products)\n"
            "5. location = WHERE it happened (be specific: city + country if available)\n"
            "6. numbers = any KEY NUMBERS mentioned (casualties, amounts, counts, percentages)\n"
            "7. confidence = how confident you are in this extraction (0.0-1.0)\n\n"
            "event_type must be one of: ATTACK, DETENTION, ELECTION, PROTEST, AGREEMENT, "
            "MERGER, ACQUISITION, POLICY, SANCTIONS, NATURAL_DISASTER, WEATHER, SPORTS, DEATH, "
            "LEGAL, HEALTH, DIPLOMACY, MILITARY_OPERATION, LAYOFF, PRODUCT_LAUNCH, "
            "INVESTMENT, ACCIDENT, SCANDAL, LEGISLATION, VIOLENCE, IPO, EARNINGS, BANKRUPTCY, "
            "SPACE, AI_TECH, DISCOVERY\n"
            "If none fit, use the closest match or a descriptive type.\n\n"
            "--- ARTICLE ---\n"
            "Title: {title}\n"
            "Content: {content}\n"
            "--- END ---\n\n"
            "Respond with ONLY a valid JSON object matching this schema:\n"
            "{\n"
            "  \"primary_event\": {\n"
            "    \"event_type\": \"<canonical type>\",\n"
            "    \"actors\": [\"<actor1>\", \"<actor2>\"],\n"
            "    \"targets\": [\"<target1>\"],\n"
            "    \"objects\": [\"<object1>\"],\n"
            "    \"location\": \"<city, country>\",\n"
            "    \"event_time\": \"<ISO 8601 or null>\",\n"
            "    \"numbers\": {\"<key>\": <value>},\n"
            "    \"confidence\": 0.85\n"
            "  },\n"
            "  \"secondary_events\": []\n"
            "}"
        ),
        "description": "Per-article structured event extraction",
    },
    {
        "stage": "entity_extraction",
        "system_prompt": None,
        "user_prompt_template": (
            "Extract ALL named entities from the following news text.\n"
            "For EACH entity, provide:\n"
            "- value: the entity text as it appears\n"
            "- type: entity type from this list:\n"
            "  PERSON, ORG, COMPANY, COUNTRY, CITY, STATE, PLACE, LOCATION, EVENT, AGREEMENT, "
            "LAW, PRODUCT, TECHNOLOGY, POLITICAL_PARTY, WEAPON, SHIP, AIRCRAFT, DATE, TIME, "
            "MONEY, PERCENTAGE, CRYPTO, SPORTS_TEAM, DISEASE, GOVERNMENT_BODY, MILITARY_UNIT\n"
            "- canonical_name: the standardized/full name (e.g., 'Rahul Gandhi' for 'Mr Gandhi')\n"
            "- confidence: 0.0-1.0\n\n"
            "CRITICAL RULES:\n"
            "1. 'MoU' or 'Memorandum of Understanding' → type: AGREEMENT\n"
            "2. Indian states like 'Andhra Pradesh', 'Tamil Nadu' → type: STATE\n"
            "3. US states like 'California', 'Texas' → type: STATE\n"
            "4. Universities and colleges → type: ORG\n"
            "5. Political parties → type: POLITICAL_PARTY\n"
            "6. Countries → type: COUNTRY\n"
            "7. Cities → type: CITY\n"
            "8. Companies/corporations → type: COMPANY\n"
            "9. Government bodies (Supreme Court, Parliament, Congress) → type: GOVERNMENT_BODY\n"
            "10. Do NOT classify organizations, places, or agreements as PERSON.\n\n"
            "--- TEXT ---\n{text}\n--- END ---\n\n"
            "Respond with ONLY valid JSON:\n"
            "{\"entities\": [{\"value\": \"...\", \"type\": \"...\", \"canonical_name\": \"...\", \"confidence\": 0.9}]}"
        ),
        "description": "High-accuracy named entity extraction",
    },
    {
        "stage": "entity_linking",
        "system_prompt": None,
        "user_prompt_template": (
            "You are an entity resolution assistant.\n"
            "Given the entity name '{name}' of type '{entity_type}', "
            "determine its canonical name and generate a specific Wikidata search query.\n\n"
            "Context from articles:\n"
            "{context}\n\n"
            "Identify what/who this entity is in the context. E.g., if it's 'Gandhi' and the context is Indian politics, "
            "canonical name is 'Rahul Gandhi' and query is 'Rahul Gandhi politician'.\n"
            "If the entity is already clear (e.g. 'United States'), "
            "canonical name is 'United States' and query is 'United States'.\n\n"
            "Respond in JSON matching this schema:\n"
            "{\"canonical_name\": \"...\", \"wikidata_search_query\": \"...\", \"description\": \"...\"}"
        ),
        "description": "Entity disambiguation and Wikidata link generation",
    },
    {
        "stage": "contradiction_detection",
        "system_prompt": None,
        "user_prompt_template": (
            "You are a factual contradiction validator for a news intelligence platform.\n"
            "Compare these two conflicting reports of the same '{fact_type}' detail:\n"
            "1. Source: {source1_name} reports: {val1}\n"
            "2. Source: {source2_name} reports: {val2}\n\n"
            "Context from the articles:\n{context}\n\n"
            "Determine if this is a true factual contradiction (e.g. Source A says Russia did it, "
            "Source B says Ukraine did it; or 15 dead vs 50 dead).\n"
            "Note: Wording differences, translation variations, or subset relationships (e.g. "
            "'15 police officers' vs '15 people' or '15 dead' vs 'at least 10 dead') are NOT contradictions.\n\n"
            "Respond in JSON matching this schema:\n"
            "{\"is_contradiction\": true/false, \"description\": \"...\", \"confidence\": 0.0-1.0}"
        ),
        "description": "Validator to confirm heuristics-flagged contradictions",
    },
    {
        "stage": "source_comparison",
        "system_prompt": None,
        "user_prompt_template": (
            "You are a professional news intelligence analyst.\n"
            "Analyze the coverage of the publisher '{src_name}' for a story.\n\n"
            "Here are the differences and coverages detected by our heuristic engines:\n"
            "1. Unique facts reported only by {src_name}: {unique_summary}\n"
            "2. Facts reported by others but omitted by {src_name}: {missing_summary}\n"
            "3. Factual contradictions involving {src_name}: {contradictions_summary}\n\n"
            "Context from the story's articles:\n{context}\n\n"
            "Based on the heuristics and the articles' context, synthesize a clean analysis.\n"
            "For 'focus_area', write a concise, professional sentence (max 100 chars, e.g. "
            "'Detailed legal proceedings and arrest details.') summarizing their coverage angle.\n"
            "For 'unique_information', 'missing_information', and 'contradictions', provide "
            "a concise, readable description. If none, return empty string.\n\n"
            "Respond in JSON matching this schema:\n"
            "{\"focus_area\": \"...\", \"unique_information\": \"...\", \"missing_information\": \"...\", \"contradictions\": \"...\"}"
        ),
        "description": "Analyze unique/missing info and stance differences per publisher",
    },
    {
        "stage": "story_analysis",
        "system_prompt": None,
        "user_prompt_template": (
            "You are an objective, expert news intelligence analyst.\n"
            "Analyze the following articles about a single news event. "
            "Your output must be completely neutral, free of editorializing, clickbait, or political bias.\n\n"
            "{articles_text}\n"
            "Synthesize this information into a single cohesive story.\n"
            "For the 'category' field, choose exactly one slug from: politics, world, business, "
            "technology, sports, entertainment, lifestyle, travel, education, health, science, weather.\n"
            "For timeline dates, use ISO 8601 format (YYYY-MM-DD) whenever possible.\n\n"
            "Respond with ONLY a valid JSON object matching this exact schema (no markdown, no code blocks):\n"
            "{\n"
            "  \"headline\": \"<neutral headline>\",\n"
            "  \"one_line_summary\": \"<1-sentence summary>\",\n"
            "  \"short_summary\": \"<1-paragraph 3-4 sentence summary>\",\n"
            "  \"detailed_summary\": \"<multi-paragraph detailed summary>\",\n"
            "  \"key_facts\": [\"fact1\", \"fact2\", \"fact3\"],\n"
            "  \"category\": \"<category>\",\n"
            "  \"timeline\": [{\"date\": \"YYYY-MM-DD\", \"description\": \"<event>\"}],\n"
            "  \"differences\": [{\"source_name\": \"<source>\", \"unique_information\": \"<text>\", \"missing_information\": \"<text>\", \"contradictions\": \"<text>\"}]\n"
            "}"
        ),
        "description": "Cohesive multi-source story synthesis and categorization",
    },
    {
        "stage": "summary_generation",
        "system_prompt": None,
        "user_prompt_template": (
            "You are an objective, expert news intelligence analyst.\n"
            "Generate a highly objective, neutral story summary using ONLY the structured event knowledge graph, "
            "timeline, source comparison, and contradictions below.\n"
            "Do NOT invent or extrapolate facts not present in this structured knowledge.\n\n"
            "--- KNOWLEDGE GRAPH ---\n{kg_str}\n\n"
            "--- TIMELINE OF EVENTS ---\n{timeline_str}\n\n"
            "--- SOURCE COVERAGE & DIFFERENCES ---\n{source_comp_str}\n\n"
            "--- DETECTED CONTRADICTIONS ---\n{contras_str}\n\n"
            "For the 'category' field, choose exactly one slug from: politics, world, business, "
            "technology, sports, entertainment, lifestyle, travel, education, health, science, weather.\n\n"
            "Respond with ONLY a valid JSON object matching this exact schema (no markdown, no code blocks):\n"
            "{\n"
            "  \"headline\": \"<neutral headline>\",\n"
            "  \"one_line_summary\": \"<1-sentence summary>\",\n"
            "  \"short_summary\": \"<1-paragraph summary>\",\n"
            "  \"detailed_summary\": \"<multi-paragraph detailed summary>\",\n"
            "  \"key_facts\": [\"fact1\", \"fact2\", \"fact3\"],\n"
            "  \"category\": \"<category>\"\n"
            "}"
        ),
        "description": "Neutral story summary generation from KG & analysis metrics",
    },
]

SOURCES = [
    {
        "name": "Reuters",
        "slug": "reuters",
        "website_url": "https://www.reuters.com",
        "rss_url": "https://www.rss.reuters.com/news/topnews",
        "country_code": "US",
    },
    {
        "name": "BBC News",
        "slug": "bbc-news",
        "website_url": "https://www.bbc.com/news",
        "rss_url": "http://feeds.bbci.co.uk/news/rss.xml",
        "country_code": "GB",
    },
    {
        "name": "TechCrunch",
        "slug": "techcrunch",
        "website_url": "https://techcrunch.com",
        "rss_url": "https://techcrunch.com/feed/",
        "country_code": "US",
    },
    {
        "name": "The Verge",
        "slug": "the-verge",
        "website_url": "https://www.theverge.com",
        "rss_url": "https://www.theverge.com/rss/index.xml",
        "country_code": "US",
    },
    {
        "name": "NDTV",
        "slug": "ndtv",
        "website_url": "https://www.ndtv.com",
        "rss_url": "https://feeds.feedburner.com/ndtvnews-top-stories",
        "country_code": "IN",
    },
    {
        "name": "The Times of India",
        "slug": "times-of-india",
        "website_url": "https://timesofindia.indiatimes.com",
        "rss_url": "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        "country_code": "IN",
    },
    {
        "name": "Hindustan Times",
        "slug": "hindustan-times",
        "website_url": "https://www.hindustantimes.com",
        "rss_url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
        "country_code": "IN",
    },
    {
        "name": "The Indian Express",
        "slug": "indian-express",
        "website_url": "https://indianexpress.com",
        "rss_url": "https://indianexpress.com/section/india/feed/",
        "country_code": "IN",
    },
    {
        "name": "Al Jazeera",
        "slug": "al-jazeera",
        "website_url": "https://www.aljazeera.com",
        "rss_url": "https://www.aljazeera.com/xml/rss/all.xml",
        "country_code": "QA",
    },
    {
        "name": "Ars Technica",
        "slug": "ars-technica",
        "website_url": "https://arstechnica.com",
        "rss_url": "https://feeds.arstechnica.com/arstechnica/index",
        "country_code": "US",
    },
    {
        "name": "The Guardian",
        "slug": "the-guardian",
        "website_url": "https://www.theguardian.com",
        "rss_url": "https://www.theguardian.com/world/rss",
        "country_code": "GB",
    },
    {
        "name": "CNN",
        "slug": "cnn",
        "website_url": "https://www.cnn.com",
        "rss_url": "http://rss.cnn.com/rss/edition.rss",
        "country_code": "US",
    },
    {
        "name": "Bloomberg",
        "slug": "bloomberg",
        "website_url": "https://www.bloomberg.com",
        "rss_url": "https://www.bloomberg.com/feed/",
        "country_code": "US",
    },
    {
        "name": "Arise News",
        "slug": "arise-news",
        "website_url": "https://www.arise.tv",
        "rss_url": "https://www.arise.tv/feed/",
        "country_code": "NG",
    },
    {
        "name": "CNBC",
        "slug": "cnbc",
        "website_url": "https://www.cnbc.com",
        "rss_url": "https://search.cnbc.com/rs/search/all/view.xml?partnerId=2000",
        "country_code": "US",
    },
    {
        "name": "DW",
        "slug": "dw",
        "website_url": "https://www.dw.com",
        "rss_url": "https://rss.dw.com/xml/rss-en-all",
        "country_code": "DE",
    },
    {
        "name": "Euro News",
        "slug": "euronews",
        "website_url": "https://www.euronews.com",
        "rss_url": "https://www.euronews.com/rss?level=theme&name=news",
        "country_code": "FR",
    },
    {
        "name": "Fox News",
        "slug": "fox-news",
        "website_url": "https://www.foxnews.com",
        "rss_url": "http://feeds.foxnews.com/foxnews/latest",
        "country_code": "US",
    },
    {
        "name": "France 24",
        "slug": "france24",
        "website_url": "https://www.france24.com",
        "rss_url": "https://www.france24.com/en/rss",
        "country_code": "FR",
    },
    {
        "name": "Press TV",
        "slug": "press-tv",
        "website_url": "https://www.presstv.ir",
        "rss_url": "https://www.presstv.ir/Default/SectionRss/14",
        "country_code": "IR",
    },
    {
        "name": "Russia Today",
        "slug": "rt",
        "website_url": "https://www.rt.com",
        "rss_url": "https://www.rt.com/rss/news/",
        "country_code": "RU",
    },
    {
        "name": "Sky News International",
        "slug": "sky-news-international",
        "website_url": "https://news.sky.com",
        "rss_url": "http://feeds.skynews.com/feeds/info/world.xml",
        "country_code": "GB",
    },
    {
        "name": "TRT World",
        "slug": "trt-world",
        "website_url": "https://www.trtworld.com",
        "rss_url": "https://www.trtworld.com/feed",
        "country_code": "TR",
    },
    {
        "name": "Voice of America",
        "slug": "voa",
        "website_url": "https://www.voanews.com",
        "rss_url": "https://www.voanews.com/api/z$gpeto-vg",
        "country_code": "US",
    },
    {
        "name": "NHK World",
        "slug": "nhk-world",
        "website_url": "https://www3.nhk.or.jp/nhkworld/",
        "rss_url": "https://www3.nhk.or.jp/nhkworld/en/news/rss.xml",
        "country_code": "JP",
    },
    {
        "name": "CGTN",
        "slug": "cgtn",
        "website_url": "https://www.cgtn.com",
        "rss_url": "https://www.cgtn.com/rss/news.xml",
        "country_code": "CN",
    },
    {
        "name": "The Hindu",
        "slug": "the-hindu",
        "website_url": "https://www.thehindu.com",
        "rss_url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "country_code": "IN",
    },
    {
        "name": "India Today",
        "slug": "india-today",
        "website_url": "https://www.indiatoday.in",
        "rss_url": "https://www.indiatoday.in/rss/1206584",
        "country_code": "IN",
    },
    {
        "name": "Republic World",
        "slug": "republic-world",
        "website_url": "https://www.republicworld.com",
        "rss_url": "https://www.republicworld.com/rss/republic-world.xml",
        "country_code": "IN",
    },
    {
        "name": "Zee News",
        "slug": "zee-news",
        "website_url": "https://zeenews.india.com",
        "rss_url": "https://zeenews.india.com/rss/india-national-news.xml",
        "country_code": "IN",
    },
    {
        "name": "ANI News",
        "slug": "ani-news",
        "website_url": "https://www.aninews.in",
        "rss_url": "https://www.aninews.in/rss/feed/",
        "country_code": "IN",
    },
]


async def seed():
    """Seed database with categories and initial news sources."""
    async with async_session_factory() as session:
        # Seed categories
        for cat_data in CATEGORIES:
            result = await session.execute(
                select(Category).where(Category.slug == cat_data["slug"])
            )
            existing = result.scalar_one_or_none()
            if not existing:
                category = Category(
                    id=uuid.uuid4(),
                    slug=cat_data["slug"],
                    name=cat_data["name"],
                    icon=cat_data["icon"],
                    created_at=datetime.utcnow(),
                )
                session.add(category)
                print(f"  ✅ Category: {cat_data['name']}")
            else:
                print(f"  ⏭️  Category already exists: {cat_data['name']}")

        # Seed sources
        for src_data in SOURCES:
            result = await session.execute(select(Source).where(Source.slug == src_data["slug"]))
            existing = result.scalar_one_or_none()
            if not existing:
                source = Source(
                    id=uuid.uuid4(),
                    name=src_data["name"],
                    slug=src_data["slug"],
                    website_url=src_data["website_url"],
                    rss_url=src_data["rss_url"],
                    country_code=src_data["country_code"],
                    active=True,
                    created_at=datetime.utcnow(),
                )
                session.add(source)
                print(f"  ✅ Source: {src_data['name']}")
            else:
                print(f"  ⏭️  Source already exists: {src_data['name']}")

        # Seed prompt templates
        for p_data in PROMPT_TEMPLATES:
            sys_p = p_data["system_prompt"] or ""
            user_p = p_data["user_prompt_template"] or ""
            combined = f"stage:{p_data['stage']}\nsys:{sys_p}\nuser:{user_p}"
            prompt_hash = hashlib.sha256(combined.encode("utf-8")).hexdigest()

            result = await session.execute(
                select(PromptVersionModel).where(PromptVersionModel.prompt_hash == prompt_hash)
            )
            existing = result.scalar_one_or_none()
            if not existing:
                # Deactivate older prompt versions for this stage
                from sqlalchemy import update
                await session.execute(
                    update(PromptVersionModel)
                    .where(PromptVersionModel.stage == p_data["stage"])
                    .values(is_active=False)
                )

                prompt_version = PromptVersionModel(
                    id=uuid.uuid4(),
                    prompt_hash=prompt_hash,
                    stage=p_data["stage"],
                    system_prompt=p_data["system_prompt"],
                    user_prompt_template=p_data["user_prompt_template"],
                    version=1,
                    description=p_data["description"],
                    is_active=True,
                    created_at=datetime.utcnow(),
                )
                session.add(prompt_version)
                print(f"  ✅ Prompt Template: {p_data['stage']}")
            else:
                print(f"  ⏭️  Prompt Template already exists: {p_data['stage']}")

        await session.commit()
    print("\n🎉 Seeding complete!")


if __name__ == "__main__":
    print("🌱 Seeding NewsIQ database...\n")
    asyncio.run(seed())
