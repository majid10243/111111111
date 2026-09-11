AI Provider Free Model Scanner v6

Important 9Router fix:
1) Enter the local 9Router URL, normally http://localhost:20128
2) Enter the 9Router Dashboard password and click Login.
3) The app authenticates through /api/auth/login and keeps the auth_token cookie only in memory.
4) Click 9Router -> Register Provider.
5) The app verifies the created provider with GET /api/providers and reports its ID.

The 9Router management API is protected by the dashboard auth cookie in current versions; sending a normal API-key Bearer token is not sufficient.

Note: Current 9Router versions have a known issue where providerSpecificData.enabledModels is read but not persisted for custom OpenAI-compatible providers. Therefore v6 does not claim that the selected-model restriction was saved. The provider itself is created and verified; 9Router can fetch the upstream model catalog.

Continue Export remains available.
