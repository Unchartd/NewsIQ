# API Cleanup Report

An audit of the FastAPI routes and endpoints defined in the application.

## Active API Sub-Routers
All routers registered in [router.py](file:///c:/Users/zakau/NewsIQ/apps/api/app/api/v1/router.py) are active:
- `/auth`: Handles user authentication and sessions.
- `/consent`: Handles cookie consent settings.
- `/users`: User settings, bookmarks, and preferences.
- `/sources`: Active news sources.
- `/stories`: Feeds, trending widgets, search, details, bookmarks, and comparisons.
- `/admin`: Moderate stories, adjust algorithms, system metrics, and roles.

## Deprecated API Endpoints
- No endpoints are currently flagged as deprecated or legacy. All endpoints are actively utilized by the frontend and admin panel.
