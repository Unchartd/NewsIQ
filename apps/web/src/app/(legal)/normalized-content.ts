export interface PolicySection {
  id: string;
  title: string;
  content: string;
}

export interface PolicyDocument {
  title: string;
  subtitle: string;
  effectiveDate: string;
  version: string;
  lawContext?: string;
  sections: PolicySection[];
}

export const normalizedPolicies: Record<string, PolicyDocument> = {
  tos: {
    title: "Terms of Service",
    subtitle: "These Terms govern your access to and use of the NewsIQ platform, APIs, and related services.",
    effectiveDate: "June 15, 2026",
    version: "v3.0",
    sections: [
      {
        id: "tos-1",
        title: "Acceptance of Terms",
        content: "These Terms constitute a legally binding agreement between you and NewsIQ. By creating an account, accessing the platform, or using the Services, you acknowledge that you have read, understood, and agree to these Terms and our Privacy Policy. If you are using the Services on behalf of an entity, you warrant that you have authority to bind that entity."
      },
      {
        id: "tos-2",
        title: "Eligibility",
        content: "You must be legally capable of entering into a binding agreement under applicable law, and be at least 13 years of age (or higher minimum age in your jurisdiction). If you are under the age of majority, you may use the Services only with the involvement and consent of a parent or guardian."
      },
      {
        id: "tos-3",
        title: "Description of the Services",
        content: "NewsIQ is an AI-powered news intelligence and comprehension platform. It aggregates publicly available information from third-party publishers and uses AI to generate neutral headlines, summaries, timelines, and comparisons. NewsIQ is not a newsroom, publisher, or source of professional advice. Copyright of original articles remains with their respective owners."
      },
      {
        id: "tos-4",
        title: "Accounts and Authentication",
        content: "Certain features require an account. You register using email or OAuth providers. You are responsible for credentials confidentiality, restricting unauthorized access, and all activities under your account. Notify NewsIQ immediately at support@newsiq.ai if you suspect unauthorized access."
      },
      {
        id: "tos-5",
        title: "Nature of AI Features",
        content: "NewsIQ uses AI and LLMs to generate insights. AI systems are probabilistic and may produce outputs that contain inaccuracies, omissions, or outdated context. AI-generated outputs are for informational purposes only. NewsIQ does not warrant accuracy, and users remain responsible for independently verifying important facts."
      },
      {
        id: "tos-6",
        title: "Third-Party Publishers and Source Attribution",
        content: "NewsIQ references and aggregates content from third-party publishers. We do not claim ownership of third-party news articles; all copyright remains with their owners. NewsIQ provides source attribution, publisher names, and links to original articles to complement, not substitute, original journalism."
      },
      {
        id: "tos-7",
        title: "Fair Use and Fair Dealing Principles",
        content: "NewsIQ operates in accordance with applicable copyright laws, fair use, and fair dealing principles. Attribution and source transparency are fundamental. Publishers may contact legal@newsiq.ai regarding copyright concerns or content usage requests."
      },
      {
        id: "tos-8",
        title: "Acceptable Use & Conduct Rules",
        content: "You agree to use the Services only in compliance with these Terms, applicable laws, and the Acceptable Use Policy. You shall not misuse the platform, interfere with its operation, or violate the rights of NewsIQ, publishers, or other users."
      },
      {
        id: "tos-9",
        title: "Prohibited Activities",
        content: "You shall not: (a) engage in illegal conduct (fraud, identity theft, harassment); (b) attempt security violations (unauthorized access, circumvent authentication, introduce malware); (c) perform automated abuse (scrape feeds, harvest data, circumvent rate limits without written permission); (d) decompile or reverse engineer software; or (e) share credentials or transfer subscriptions without authorization."
      },
      {
        id: "tos-10",
        title: "Anti-Scraping Policy",
        content: "Unauthorized scraping, crawling, or automated extraction of NewsIQ feeds, summaries, timelines, rankings, metadata, and analytical outputs is strictly prohibited. Users may not use NewsIQ data to train machine learning systems or create derivative datasets without prior written authorization from legal@newsiq.ai."
      },
      {
        id: "tos-11",
        title: "User Content License",
        content: "You retain ownership of comments, bookmarks, preferences, or other materials you submit ('User Content'). You grant NewsIQ a limited, non-exclusive, worldwide, royalty-free license to store, process, display, and use User Content solely for providing and improving the Services, personalization, and security."
      },
      {
        id: "tos-12",
        title: "Intellectual Property Rights",
        content: "Except for third-party content and User Content, all rights in the Services (software, design, branding, user interfaces, AI-generated analytical structures, and taxonomies) belong to NewsIQ. No ownership rights are transferred to users."
      },
      {
        id: "tos-13",
        title: "Third-Party Content Disclaimer",
        content: "NewsIQ does not control or guarantee the accuracy, completeness, or availability of third-party content. Accessing external websites linked from NewsIQ is at your own risk and subject to those sites' policies."
      },
      {
        id: "tos-14",
        title: "Beta Features",
        content: "NewsIQ may release experimental or beta features. Beta features are provided 'as is' and may change, contain unexpected results, or become unavailable. NewsIQ has no obligation to continue supporting beta features."
      },
      {
        id: "tos-15",
        title: "User Feedback",
        content: "If you submit suggestions or feedback, you grant NewsIQ a perpetual, worldwide, irrevocable, royalty-free right to use and implement such feedback without compensation or obligation."
      },
      {
        id: "tos-16",
        title: "Subscription Plans & Access Quotas",
        content: "NewsIQ offers Free, Premium, and Enterprise plans. Quotas, features, and limits for the Free plan may change at any time without liability. Premium and Enterprise features are subject to subscription billing terms."
      },
      {
        id: "tos-17",
        title: "Payments and Billing",
        content: "Paid subscriptions authorize NewsIQ and its payment processors (e.g. Razorpay, Stripe) to charge the applicable fees and taxes. Fees are billed in the currency displayed at checkout. You are responsible for maintaining accurate billing information; failure to do so may result in suspension."
      },
      {
        id: "tos-18",
        title: "Automatic Renewal & Cancellation",
        content: "Subscriptions automatically renew at the end of each billing cycle using the payment method on file. You may cancel renewal at any time through Settings before the next billing period starts. Cancellation prevents future charges but does not entitle you to refunds for previously paid periods."
      },
      {
        id: "tos-19",
        title: "Refund Policy",
        content: "Except where required by applicable law, subscription fees are non-refundable. Refunds, credits, or adjustments may be granted at NewsIQ's sole discretion. Repeated or abusive refund requests will be denied."
      },
      {
        id: "tos-20",
        title: "Changes to Pricing and Services",
        content: "NewsIQ may modify pricing, features, quotas, or subscription structures. Material changes will be communicated in advance, and continued use constitutes acceptance. We reserve the right to retire or modify features to improve the platform."
      },
      {
        id: "tos-21",
        title: "Suspension and Termination",
        content: "NewsIQ may suspend or terminate your access immediately if you violate these Terms, if fraudulent activity or security risks arise, if payments fail, or if required by law. Users may terminate their account at any time via Settings."
      },
      {
        id: "tos-22",
        title: "Copyright Policy and DMCA",
        content: "If you believe your copyright is infringed, submit a formal notice to legal@newsiq.ai containing: identification of work, description of infringing material, URL location, contact info, good-faith statement, perjury statement, and signature."
      },
      {
        id: "tos-23",
        title: "Counter-Notification Procedure",
        content: "If your content was removed in error, you may submit a counter-notice to legal@newsiq.ai containing: identification of removed material, contact info, statement under penalty of perjury, and consent to jurisdiction."
      },
      {
        id: "tos-24",
        title: "Repeat Infringer Policy",
        content: "NewsIQ will suspend or terminate accounts of users who repeatedly violate intellectual property rights. NewsIQ reserves sole discretion in determining violations."
      },
      {
        id: "tos-25",
        title: "Disclaimer of Warranties",
        content: "THE SERVICES ARE PROVIDED 'AS IS' AND 'AS AVAILABLE.' TO THE MAXIMUM EXTENT PERMITTED BY LAW, NEWSIQ DISCLAIMS ALL WARRANTIES, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, NON-INFRINGEMENT, ACCURACY, AVAILABILITY, RELIABILITY, SECURITY, OR PERFORMANCE. WE DO NOT WARRANT THE SERVICES WILL BE UNINTERRUPTED OR ERROR-FREE."
      },
      {
        id: "tos-26",
        title: "Limitation of Liability",
        content: "TO THE MAXIMUM EXTENT PERMITTED BY LAW, NEWSIQ AND ITS AFFILIATES SHALL NOT BE LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR EXEMPLARY DAMAGES, INCLUDING LOSS OF PROFITS, DATA, OR BUSINESS INTERRUPTION. NEWSIQ SHALL NOT BE LIABLE FOR DECISIONS MADE IN RELIANCE ON AI-GENERATED OUTPUTS OR PUBLISHER CONTENT. NEWSIQ'S AGGREGATE LIABILITY SHALL NOT EXCEED THE AMOUNT PAID BY YOU DURING THE 12 MONTHS PRECEDING THE CLAIM."
      },
      {
        id: "tos-27",
        title: "Indemnification",
        content: "You agree to indemnify and hold harmless NewsIQ, its officers, employees, and contractors from claims, damages, losses, and expenses arising out of: (a) your use of the Services; (b) violation of these Terms; (c) violation of law; (d) infringement of third-party rights; or (e) decisions based on AI outputs."
      },
      {
        id: "tos-28",
        title: "Force Majeure",
        content: "NewsIQ shall not be liable for delays or failures caused by events beyond its reasonable control, including natural disasters, internet outages, cyberattacks, governmental actions, labor disputes, or war."
      },
      {
        id: "tos-29",
        title: "Governing Law and Dispute Resolution",
        content: "These Terms shall be governed by and construed in accordance with the laws of India. The parties shall first attempt to resolve disputes through good-faith negotiations. If negotiations fail, disputes shall be submitted to the competent courts in Bangalore, India."
      },
      {
        id: "tos-30",
        title: "Miscellaneous provisions",
        content: "If any provision is held unenforceable, the remaining provisions remain in full force. Failure to enforce any provision is not a waiver. These Terms, the Privacy Policy, and additional agreements constitute the entire agreement. We may update these Terms periodically, and continued use constitutes acceptance."
      }
    ]
  },
  privacy: {
    title: "Privacy Policy",
    subtitle: "This policy explains exactly what data we collect, why, and what control you have over it.",
    effectiveDate: "June 15, 2026",
    version: "v3.0",
    lawContext: "DPDP Act 2023 / GDPR / CCPA",
    sections: [
      {
        id: "priv-1",
        title: "Scope & Who We Are",
        content: "This Privacy Policy applies to the NewsIQ website, user accounts, applications, APIs, and daily digests. It does not apply to third-party services. NewsIQ Technologies Private Limited (Bangalore, India) acts as the Data Fiduciary under the DPDP Act 2023 and Data Controller under GDPR. Contact us at privacy@newsiq.ai."
      },
      {
        id: "priv-2",
        title: "Information We Collect",
        content: "We collect: (a) Authentication data (email, name, OAuth identifiers); (b) Account preferences (theme, language, topics); (c) Behavioral data (reading history, clicks, search queries, bookmarks) to personalize feeds; (d) Technical details (IP address truncated, user-agent, error logs) for security; (e) Billing data (payment method type, last 4 digits) handled by Razorpay/Stripe."
      },
      {
        id: "priv-3",
        title: "How We Use Information",
        content: "We use information to: (a) Deliver and personalize the Services; (b) Monitor security, detect fraud, and prevent unauthorized scraping; (c) Aggregate anonymous telemetry to improve functionality; (d) Process subscriptions and invoice payments; (e) Comply with legal requirements."
      },
      {
        id: "priv-4",
        title: "Personalization and Profiling",
        content: "Reading activity and topic preferences are used on-platform to generate personalized feeds. This processing may constitute profiling under certain privacy laws. NewsIQ does not use profiling to make decisions that produce legal or similarly significant effects. Users may opt out in Settings."
      },
      {
        id: "priv-5",
        title: "AI Processing Disclosures",
        content: "NewsIQ uses AI models (OpenAI, Google Gemini) to summarize articles. To protect privacy, we minimize personal information sent to AI providers; we only transmit article text and metadata. User identifiers are stripped. AI outputs are probabilistic and should be verified."
      },
      {
        id: "priv-6",
        title: "Data Minimization Policy",
        content: "NewsIQ collects and processes only the information necessary for providing and improving the platform. We avoid excessive collection and regularly prune logs and user-specific tracking records."
      },
      {
        id: "priv-7",
        title: "Redis Sessions and Security",
        content: "NewsIQ uses Redis-based session tokens to manage authentication, maintain active sessions, and protect account security. Redis session data is temporary and automatically expires after a period of user inactivity."
      },
      {
        id: "priv-8",
        title: "Cookies and Local Storage",
        content: "We use essential cookies (for authentication and preferences) and privacy-focused analytics cookies (to measure feature engagement). We do not set third-party marketing or cross-site tracking cookies. Manage cookie preferences using the Cookie Settings panel."
      },
      {
        id: "priv-9",
        title: "Third-Party Service Providers",
        content: "We share data with infrastructure hosts (AWS Mumbai), payment processors (Razorpay, Stripe), transactional email providers (Postmark), and error trackers (Sentry). These partners are bound by Data Processing Agreements and may only use data to provide services."
      },
      {
        id: "priv-10",
        title: "Legal Bases for Processing (GDPR & DPDP Act)",
        content: "Under GDPR and DPDP Act 2023, processing is based on: (a) Consent (reading history, cookies); (b) Contractual Necessity (account management, billing); (c) Legitimate Interest (security monitoring, debugging); (d) Legal Obligation (billing tax logs)."
      },
      {
        id: "priv-11",
        title: "International Data Transfers",
        content: "Primary personal data is stored on AWS servers in Mumbai, India. If data is transferred outside your jurisdiction (e.g. error traces to Sentry in the US), we enforce Standard Contractual Clauses and security safeguards to protect the data."
      },
      {
        id: "priv-12",
        title: "Marketing and Communications",
        content: "You may receive operational emails (billing, security). If you opt in, we may send product updates. You can unsubscribe from marketing communications at any time via the link in the footer or in Settings."
      },
      {
        id: "priv-13",
        title: "Data Retention Periods",
        content: "Account details are kept while active. Reading history is pruned on a 12-month rolling basis. Telemetry logs are stored for 30 days. Billing logs are kept for 7 years to meet tax obligations. Support tickets are retained for 2 years."
      },
      {
        id: "priv-14",
        title: "Account Deletion (Right to Erasure)",
        content: "You can request account deletion in Settings. Upon request, NewsIQ permanently anonymizes your personal information (name, email, OAuth data) and deletes associated preferences, bookmarks, and search history within 30 days."
      },
      {
        id: "priv-15",
        title: "Data Portability",
        content: "You may download a structured JSON export of your bookmarks, reading logs, and settings at any time from Settings -> Privacy."
      },
      {
        id: "priv-16",
        title: "Your Rights (GDPR & UK GDPR)",
        content: "GDPR grants rights to: Access, Rectification, Erasure, Restriction, Portability, Objection, and to lodge a complaint with your local supervisory authority. Contact privacy@newsiq.ai to exercise these rights."
      },
      {
        id: "priv-17",
        title: "California Privacy Rights (CCPA / CPRA)",
        content: "California residents have the right to Know, Access, Correct, Delete, and Opt-Out of data sharing/selling. NewsIQ does not sell or share personal information. You can submit requests using the privacy request form."
      },
      {
        id: "priv-18",
        title: "India DPDP Act 2023 Rights",
        content: "Indian citizens have the Right to Access, Correction, Erasure, Grievance Redressal, and the Right to Nominate another individual to act on their behalf. Submit nominations to privacy@newsiq.ai. Grievance Officer: Aarav Mehta (CEO), Bangalore."
      },
      {
        id: "priv-19",
        title: "Children's Privacy",
        content: "NewsIQ does not knowingly collect personal data from children under 13. For teenagers under 18, tracking features are disabled by default and parental consent is required for subscriptions."
      },
      {
        id: "priv-20",
        title: "Security Safeguards",
        content: "We enforce HTTPS (TLS 1.3), bcrypt password hashing, role-based access control, MFA for administrators, and continuous infrastructure logging to prevent unauthorized access."
      },
      {
        id: "priv-21",
        title: "Security Incident Response",
        content: "In the event of a confirmed data breach that threatens your rights, we will notify you and relevant regulatory authorities within 72 hours, detailing the scope and mitigation measures."
      }
    ]
  },
  cookies: {
    title: "Cookie Policy",
    subtitle: "This Cookie Policy explains how and why we use cookies and local storage.",
    effectiveDate: "June 15, 2026",
    version: "v3.0",
    sections: [
      {
        id: "cook-1",
        title: "What are Cookies?",
        content: "Cookies are small text files placed on your device. Session cookies are temporary and expire when you close your browser. Persistent cookies remain for a set period. We also use browser local storage to save user preferences."
      },
      {
        id: "cook-2",
        title: "Essential Cookies We Set",
        content: "Essential cookies are required for core platform functions: (a) `niq_session` (stores your authentication session token); (b) `niq_theme` (remembers dark/light mode); (c) `niq_prefs` (saves summary length and layout settings). Disabling them prevents login."
      },
      {
        id: "cook-3",
        title: "Analytics Cookies We Set",
        content: "Analytics cookies help us measure engagement anonymously: (a) `niq_analytics` (tracks feature clicks and time spent, expires in 90 days); (b) `niq_ab` (assigns A/B testing groups, expires in 30 days). You can opt out in Cookie Settings."
      },
      {
        id: "cook-4",
        title: "Redis Session Storage",
        content: "For security, we maintain session states inside a Redis cache on the server. Your browser's essential cookie maps to the active Redis token, which automatically expires after inactivity to protect your account."
      },
      {
        id: "cook-5",
        title: "Third-Party Cookies",
        content: "Third-party services (Razorpay, Stripe) set essential functional cookies to process payments securely. NewsIQ does not allow third-party advertising or cross-site tracking cookies."
      },
      {
        id: "cook-6",
        title: "Managing Cookie Preferences",
        content: "You can customize cookies by clicking 'Cookie Settings' in the site footer. Non-essential analytics and functional tracking can be toggled on or off instantly. You can also block cookies via your browser configurations."
      }
    ]
  },
  aup: {
    title: "Acceptable Use Policy",
    subtitle: "Our rules of conduct for maintaining a safe and lawful platform for everyone.",
    effectiveDate: "June 15, 2026",
    version: "v3.0",
    sections: [
      {
        id: "aup-1",
        title: "Lawful Use Only",
        content: "You may use NewsIQ only for lawful and authorized purposes. You must comply with all applicable local, national, and international laws and regulations."
      },
      {
        id: "aup-2",
        title: "Prohibited Content & Actions",
        content: "You shall not use NewsIQ to: (a) engage in fraud, impersonation, or money laundering; (b) harass, abuse, or threaten other users; (c) distribute harmful, offensive, or defamatory content; (d) bypass rate limits, access accounts without authorization, or share access credentials."
      },
      {
        id: "aup-3",
        title: "Scraping & System Abuse",
        content: "Crawling, scraping, harvesting, or extracting content from NewsIQ using bots, automated scripts, or browser extensions is strictly prohibited. You may not use NewsIQ outputs to train machine learning systems or compile databases."
      },
      {
        id: "aup-4",
        title: "Security Prohibitions",
        content: "You may not: (a) probe, scan, or test the vulnerability of our systems; (b) conduct denial-of-service (DoS) attacks; (c) introduce malware, trojans, or spyware; (d) attempt to decompile, disassemble, or reverse engineer any software."
      },
      {
        id: "aup-5",
        title: "AI Misuse",
        content: "You shall not use NewsIQ AI features to spread misinformation, conduct propaganda, manipulate public opinion, or generate deceptive or harmful content."
      },
      {
        id: "aup-6",
        title: "Enforcement and Reporting",
        content: "Violation of these rules may result in rate-limiting, suspension, or permanent termination of your account. Report suspected abuse to support@newsiq.ai."
      }
    ]
  },
  disclaimer: {
    title: "Disclaimer Policy",
    subtitle: "Please read this disclaimer to understand the limitations of our platform and outputs.",
    effectiveDate: "June 15, 2026",
    version: "v3.0",
    sections: [
      {
        id: "disc-1",
        title: "Informational Purposes Only",
        content: "NewsIQ is an intelligence tool designed to help you analyze developing news stories. All information, summaries, and timelines are provided 'as is' for general information purposes only."
      },
      {
        id: "disc-2",
        title: "No Professional Advice",
        content: "NewsIQ is not a licensed advisor. Nothing on the platform constitutes: (a) legal advice; (b) financial or investment recommendations; (c) medical diagnostics or health advice. Consult qualified professionals for these decisions."
      },
      {
        id: "disc-3",
        title: "AI Limitations & Accuracy Disclaimer",
        content: "Summaries and difference analysis are generated by artificial intelligence. AI models are probabilistic. They can produce hallucinations, omit facts, contain outdated references, or misinterpret article context. Verify facts using the provided publisher links."
      },
      {
        id: "disc-4",
        title: "Third-Party Content Disclaimer",
        content: "NewsIQ references, aggregates, and links to external publisher websites. NewsIQ does not review, control, or endorse these third parties and is not responsible for their content, reliability, accuracy, or security."
      },
      {
        id: "disc-5",
        title: "Platform Availability Disclaimer",
        content: "We strive to maintain high availability but do not warrant that the Services will be uninterrupted, error-free, secure, or free from server maintenance downtime."
      }
    ]
  },
  dmca: {
    title: "Copyright & DMCA Policy",
    subtitle: "Our procedures for responding to allegations of copyright infringement.",
    effectiveDate: "June 15, 2026",
    version: "v3.0",
    sections: [
      {
        id: "dmca-1",
        title: "Copyright Ownership",
        content: "NewsIQ respects the intellectual property rights of publishers. We aggregate, summarize, and attribute third-party articles under principles of fair use. All copyright and ownership remain with the original publishers and rights holders."
      },
      {
        id: "dmca-2",
        title: "Submitting a DMCA Notice",
        content: "If you are a copyright owner and believe that material on NewsIQ infringes your rights, submit a written takedown request to legal@newsiq.ai. Include: (a) physical/electronic signature; (b) identification of work; (c) URL of infringing material; (d) contact details; (e) good-faith belief statement; (f) perjury statement."
      },
      {
        id: "dmca-3",
        title: "Content Removal Procedure",
        content: "Upon receiving a valid and complete infringement notice, NewsIQ will promptly remove or disable access to the disputed material and notify the affected user."
      },
      {
        id: "dmca-4",
        title: "Counter-Notice Procedure",
        content: "If you believe your content was removed in error, submit a counter-notice to legal@newsiq.ai containing: (a) identification of removed material; (b) contact info; (c) statement under penalty of perjury; (d) consent to jurisdiction; (e) signature."
      },
      {
        id: "dmca-5",
        title: "Repeat Infringer Policy",
        content: "NewsIQ will terminate account privileges for any user who repeatedly infringes copyright rules or ignores acceptable use terms."
      }
    ]
  },
  subscription: {
    title: "Subscription & Billing Policy",
    subtitle: "This policy details subscription terms, automatic renewals, and cancellation procedures.",
    effectiveDate: "June 15, 2026",
    version: "v3.0",
    sections: [
      {
        id: "sub-1",
        title: "Subscription Plans",
        content: "We offer three plans: (a) Free Plan (limited summary depths, standard feeds); (b) Premium Plan (unlimited AI analysis, advanced summaries, personalized digest); (c) Enterprise Plan (team controls, custom integrations, API keys)."
      },
      {
        id: "sub-2",
        title: "Billing Cycles & Payment",
        content: "Paid subscriptions are billed on a recurring monthly or annual basis, as selected at checkout. You authorize NewsIQ and its payment processors to charge your payment method. You must keep billing details accurate."
      },
      {
        id: "sub-3",
        title: "Automatic Renewal",
        content: "Subscriptions automatically renew at the end of each billing cycle unless you cancel before your renewal date. The renewal charge matches the active rate of the plan unless communicated otherwise."
      },
      {
        id: "sub-4",
        title: "Cancellation Procedure",
        content: "You can cancel your subscription at any time through Settings -> Subscription. Cancellation stops automatic renewals; you will retain Premium features until the end of the current billing period."
      },
      {
        id: "sub-5",
        title: "Refund Policy",
        content: "Subscription fees are non-refundable and we do not issue partial billing period refunds. NewsIQ may issue credits or refunds in special cases at its sole discretion."
      },
      {
        id: "sub-6",
        title: "Price & Plan Modifications",
        content: "NewsIQ may change pricing or plan limits. We will notify active subscribers 30 days in advance of pricing changes. Continued use constitutes acceptance."
      }
    ]
  },
  retention: {
    title: "Data Retention & Deletion Policy",
    subtitle: "Detailed information on how long we store different types of user data.",
    effectiveDate: "June 15, 2026",
    version: "v3.0",
    sections: [
      {
        id: "ret-1",
        title: "Policy Purpose",
        content: "We aim to retain your data only for as long as necessary to provide service, maintain account security, or comply with legal requirements."
      },
      {
        id: "ret-2",
        title: "Retention Timelines",
        content: "Timelines: (a) Account data: active account lifetime + 30 days; (b) Reading history: rolling 12 months; (c) Telemetry and server logs: 30 days; (d) Billing transactions: 7 years (under Indian tax laws); (e) Support tickets: 2 years."
      },
      {
        id: "ret-3",
        title: "Account Deletion Process",
        content: "When you request account deletion, we immediately initiate a scrub. Within 30 days, we permanently anonymize personal identifiers and delete bookmarks, preferences, and events from primary databases. Backups purge within 90 days."
      },
      {
        id: "ret-4",
        title: "Data Portability Right",
        content: "You may request a copy of your personal data in JSON format from Settings -> Privacy. Requests are processed automatically and downloadable instantly."
      }
    ]
  },
  ai: {
    title: "Security & Responsible AI Statement",
    subtitle: "Our commitments to AI safety, accountability, and system security.",
    effectiveDate: "June 15, 2026",
    version: "v3.0",
    sections: [
      {
        id: "ai-1",
        title: "Our AI Mission",
        content: "NewsIQ aims to build trustworthy AI tools to improve news comprehension. We design systems to complement original journalism, respect copyright, and manage AI limitations responsibly."
      },
      {
        id: "ai-2",
        title: "Responsible AI Principles",
        content: "Our AI principles are: (a) Transparency (clearly labeling AI outputs); (b) Human Oversight (AI supports, never replaces, human judgment); (c) Neutrality (striving to present balanced summaries across multiple sources)."
      },
      {
        id: "ai-3",
        title: "System Safety & Bias Mitigation",
        content: "AI models can reflect biases. We implement custom prompt templates and feed source diversity to reduce political or regional bias, and regularly test outputs for balance."
      },
      {
        id: "ai-4",
        title: "Technical Security Safeguards",
        content: "We secure our systems using: (a) HTTPS TLS 1.3 encryption in transit; (b) AES-256 database encryption at rest; (c) Bcrypt password hashing; (d) Rate-limiting and active logging to block scraping and abuse."
      },
      {
        id: "ai-5",
        title: "Security Incident Response",
        content: "We monitor systems continuously. In the event of a vulnerability or security breach, our incident response team works to isolate the issue and notify affected users within 72 hours."
      }
    ]
  },
  attribution: {
    title: "Content Attribution & Source Transparency",
    subtitle: "How we attribute original news sources and maintain transparency.",
    effectiveDate: "June 15, 2026",
    version: "v3.0",
    sections: [
      {
        id: "attr-1",
        title: "Attribution Principles",
        content: "Attribution is core to NewsIQ. We always: (a) identify the original publisher; (b) display the source logo (where available); (c) provide a direct link to the original article; (d) show publication timestamps."
      },
      {
        id: "attr-2",
        title: "AI Summaries as Context",
        content: "NewsIQ AI-generated headlines and summaries are designed to add context and help users identify important updates. They are transformative and complement rather than replace the publisher's work."
      },
      {
        id: "attr-3",
        title: "Source Diversity Commitments",
        content: "We expose users to stories from multiple perspectives and publishers to reduce echo chambers and promote source transparency."
      },
      {
        id: "attr-4",
        title: "Publisher Control & Opt-Out",
        content: "Publishers with concerns regarding copyright, attribution formats, or scraping limits can contact legal@newsiq.ai. We address concerns in good faith."
      }
    ]
  }
};
