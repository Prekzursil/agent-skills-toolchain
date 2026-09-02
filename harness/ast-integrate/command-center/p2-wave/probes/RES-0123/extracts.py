"""Fallback extracts for hosts that return HTTP 403 to this worktree's urllib.

Live urllib status is still recorded. These strings are the MCP webfetch
extracts of the same official URLs, stored so quotes remain re-checkable.
They are not a legal opinion and are not a substitute for the live HTML
when the live HTML is obtainable.
"""

OPENAI_SERVICES = """
Effective: January 1, 2026
This OpenAI Services Agreement only applies to use of OpenAI’s APIs, ChatGPT Enterprise, ChatGPT Business, ChatGPT for Clinicians, and other services for customers who are businesses and developers, and does not apply to OpenAI services used by consumers or individuals unless specified above.
2.2. Use. OpenAI grants Customer a non-exclusive right to access and use the Services during the Term. This includes the right to use OpenAI’s API to integrate the Services into Customer Applications and to make Customer Applications available to End Users.
3.1. Customer Account. Customer must provide accurate and current Account information. Customer will not share Account access credentials or individual login credentials between multiple users. Customer may not resell or lease access to its Account or any End User Account. Customer will promptly notify OpenAI if it becomes aware of unauthorized access to the Account or the Services.
3.3. Restrictions. Customer will not, and will not permit End Users to: (h) interfere with or disrupt the Services, including circumvent any rate limits or restrictions or bypass any protective measures or safety mitigations for the Services; (i) violate or circumvent Usage Limits or otherwise configure the Services to avoid Usage Limits.
""".strip()

OPENAI_CONSUMER = """
Effective: January 1, 2026 (Previous version)
These Terms of Use apply to your use of ChatGPT, DALL·E, and OpenAI’s other services for individuals, along with any associated software applications and websites (all together, “Services”).
Our Business Terms govern use of ChatGPT Enterprise, our APIs, and our other services for businesses and developers.
Registration. You must provide accurate and complete information to register for an account to use our Services. You may not share your account credentials or make your account available to anyone else and are responsible for all activities that occur under your account.
""".strip()

XAI_CONSUMER = """
Effective: June 26, 2026 (previous version)
These Terms of Service (“Terms”) apply to your or others’ access, interactions and/or use of Grok, Grokipedia, and xAI’s other services for individuals.
Our Enterprise Terms of Service govern the use of our Services for developers and businesses, including xAI APIs and PromptIDE.
Registration. You must provide accurate and complete information to register for an account to use our Service. You may not share your account credentials or make your account available to anyone else, and are responsible for all activities that occur under your account.
""".strip()

GROQ_SERVICES = """
This Groq Services Agreement (the “Agreement”) is entered as of the Effective Date between the person or entity agreeing to the Agreement (“you”, or “Customer”) and the Groq Contracting Party.
Cloud Services and the AI Model Services under this Agreement are not for consumer use.
“Groq’s APIs” means any application programming interface provided by Groq as part of the Cloud Services.
3.1 Cloud Services Use. Subject to Customer’s ongoing compliance with the terms and conditions of this Agreement, Groq grants you a non-exclusive, non-transferable, and limited right to access and use the Cloud Services, including the right to use Groq’s APIs to integrate the Cloud Services and AI Model Services into your Customer Application.
3.2 Accounts. Customer must have an Account to use the Cloud Services and is responsible for the information it provides to create the Account, the security of its passwords for the Account (including any keys for Groq’s APIs), and for any use of its Account. Customer will only make its Account available to Authorized Account Users. Customer may not resell or lease access to its Account.
""".strip()
