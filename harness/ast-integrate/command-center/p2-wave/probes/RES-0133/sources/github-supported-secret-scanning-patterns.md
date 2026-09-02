# Supported secret scanning patterns

Lists of supported secrets and the partners that GitHub works with to prevent fraudulent use of secrets that were committed accidentally.

## About secret scanning patterns

There are three types of secret scanning alerts:

* **User alerts:** Reported to users in the ** Security and quality** tab of the repository, when a supported secret is detected in the repository.
* **Push protection alerts:** Reported to users in the ** Security and quality** tab of the repository, when a contributor bypasses push protection.
* **Partner alerts:** Reported directly to secret providers that are part of secret scanning's partner program. These alerts are not reported in the ** Security and quality** tab of the repository.

For in-depth information about each alert type, see [About secret scanning alerts](/en/code-security/concepts/secret-security/about-alerts).

If you use the REST API for secret scanning, you can use the `Secret type` to report on secrets from specific issuers. For more information, see [REST API endpoints for secret scanning](/en/enterprise-cloud@latest/rest/secret-scanning).

### Pattern categories

| Category | Description | Detection approach | Example |
| --------------- | --------------------------------------------------------------------------------------------- | ------------------ | ------------------- |
| **Generic** | Secrets not tied to a specific provider, such as private keys and database connection strings | Regex-based | `rsa_private_key` |
| **AI-detected** | Passwords and other unstructured secrets detected using AI models | AI-based | `password` |
| **Provider** | Secrets tied to a specific service provider (such as AWS, Azure, Stripe) | Regex-based | `aws_access_key_id` |

### Capabilities by category

| Capability | Generic patterns | AI-detected | Provider patterns |
| ------------------------------ | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: | :-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------: |
| User alerts | | | |
| Partner notifications | | | (if partner) |
| Push protection (default) | | | (most) |
| Push protection (configurable) | | | Some |
| Validity checks | | | Some |
| Extended metadata | | | Some |
| Base64 format support | | | Some |

> \[!NOTE]
> Validity and extended metadata checks are only available to users with GitHub Team or GitHub Enterprise who enable the feature as part of GitHub Secret Protection.

## Supported generic patterns

Precision levels are estimated based on the pattern type's typical false positive rates.

| Provider | Token | Description | Precision |
| :------- | :----------------------------------- | :--------------------------------------------------------------------- | :-------- |
| Generic | ec\_private\_key | Elliptic Curve (EC) private keys used for cryptographic operations | High |
| Generic | generic\_private\_key | Cryptographic private keys with `-----BEGIN PRIVATE KEY-----` header | High |
| Generic | http\_basic\_authentication\_header | HTTP Basic Authentication credentials in request headers | Medium |
| Generic | http\_bearer\_authentication\_header | HTTP Bearer tokens used for API authentication | Medium |
| Generic | mongodb\_connection\_string | Connection strings for MongoDB databases containing credentials | High |
| Generic | mysql\_connection\_url | Connection strings for MySQL databases containing credentials | High |
| Generic | openssh\_private\_key | OpenSSH format private keys used for SSH authentication | High |
| Generic | pgp\_private\_key | PGP (Pretty Good Privacy) private keys used for encryption and signing | High |
| Generic | postgres\_connection\_string | Connection strings for PostgreSQL databases containing credentials | High |
| Generic | rsa\_private\_key | RSA private keys used for cryptographic operations | High |

> \[!NOTE]
> Validity checks are **not supported** for generic patterns.

## Supported AI-detected patterns

Secret scanning uses Copilot to detect generic secrets using AI. See [Application card: GitHub security and quality AI features](/en/code-security/responsible-use/security-and-quality-ai-features).

| Provider | Token |
| -------- | :------- |
| Generic | password |

> \[!NOTE] Push protection and validity checks are not supported for passwords.

## Supported provider patterns

Use the table below to search, filter, and browse all supported patterns. You can filter by provider name, push protection support, validity checks, and more.

> \[!NOTE] Service providers update the patterns used to generate tokens periodically and may support more than one version of a token. Push protection only supports the most recent token versions that secret scanning can identify with confidence. This avoids push protection blocking commits unnecessarily when a result may be a false positive, which is more likely to happen with legacy tokens.

## Supported patterns

| Provider | Secret | Secret type | Partner | User alert | Push protection | Validity check | Metadata | Base64 |
| --- | --- | --- | :---: | :---: | :---: | :---: | :---: | :---: |
| 1Password | 1Password Service Account Token | 1password_service_account_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Adafruit | Adafruit IO Key | adafruit_io_key | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Adobe | Adobe Client Secret | adobe_client_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Adobe | Adobe Device Token | adobe_device_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Adobe | Adobe PAC Token | adobe_pac_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Adobe | Adobe Refresh Token | adobe_refresh_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Adobe | Adobe Service Token | adobe_service_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Adobe | Adobe Short-Lived Access Token | adobe_short_lived_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Aikido | Aikido API Client Secret | aikido_api_client_secret | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Aikido | Aikido CI Scanning Token | aikido_ci_scanning_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Airtable | Airtable API Key | airtable_api_key | ✗ | ✓ | ✓ | ✗ | ✓ | ✗ |
| Airtable | Airtable Personal Access Token | airtable_personal_access_token | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Aiven | Aiven Auth Token | aiven_auth_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Aiven | Aiven Service Password | aiven_service_password | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Alibaba | Alibaba Cloud AccessKey ID | alibaba_cloud_access_key_id, alibaba_cloud_access_key_secret | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Amazon AWS | Amazon AWS Access Key ID | aws_access_key_id, aws_secret_access_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Amazon AWS | Amazon AWS API Key ID | aws_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Amazon AWS | Amazon AWS Session Token | aws_secret_access_key, aws_session_token, aws_temporary_access_key_id | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Anthropic | Anthropic Admin API Key | anthropic_admin_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Anthropic | Anthropic API Key | anthropic_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Anthropic | Anthropic Session ID | anthropic_session_id | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| APIclub | APIclub API Key | apiclub_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Apify | Apify Actor Run API Token | apify_actor_run_api_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Apify | Apify Actor Run Proxy Password | apify_actor_run_proxy_password | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Apify | Apify API Token | apify_api_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Apify | Apify Integration API Token | apify_integration_api_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Apify | Apify Proxy Password | apify_proxy_password | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Apify | Apify UI Token | apify_ui_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Apify | Apify Webhook Dispatch API Token | apify_webhook_dispatch_api_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Asaas | Asaas API Token | asaas_api_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Asana | Asana Legacy Format Personal Access Token | asana_legacy_format_personal_access_token | ✗ | ✓ | ✗ | ✓ | ✓ | ✗ |
| Asana | Asana Personal Access Token | asana_personal_access_token, [Token versions](#token-versions) | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Atlassian | Atlassian API Token | atlassian_api_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Atlassian | Atlassian JSON Web Token | atlassian_jwt | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Authress | Authress Service Client Access Key | authress_service_client_access_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Active Directory Application Secret | azure_active_directory_application_secret, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure AI Services Key | azure_ai_services_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Anomaly Detector EE Key | azure_anomaly_detector_ee_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Anomaly Detector Key | azure_anomaly_detector_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Apim Direct Management Key | azure_apim_direct_management_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Apim Gateway Key | azure_apim_gateway_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Apim Repository Key | azure_apim_repository_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Apim Subscription Key | azure_apim_subscription_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure App Configuration Connection String | azure_app_configuration_connection_string | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure App Configuration Key | azure_app_configuration_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Batch Key Identifiable | azure_batch_key_identifiable, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Cache for Redis Access Key | azure_cache_for_redis_access_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Azure | Azure Cognitive Services Key | azure_cognitive_services_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Communication Services Connection String | azure_communication_services_connection_string | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Communication Services Key | azure_communication_services_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Computer Vision Key | azure_computer_vision_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Registry Key Identifiable | azure_container_registry_key_identifiable | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Content Moderator Key | azure_content_moderator_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Content Safety Key | azure_content_safety_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Cosmosdb Key Identifiable | azure_cosmosdb_key_identifiable, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Azure | Azure Custom Vision Prediction Key | azure_custom_vision_prediction_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Custom Vision Training Key | azure_custom_vision_training_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure DevOps Personal Access Token | azure_devops_personal_access_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Event Grid Key Identifiable | azure_event_grid_key_identifiable, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Event Hub Key Identifiable | azure_event_hub_key_identifiable | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Face Key | azure_face_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Fluid Relay Key | azure_fluid_relay_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Form Recognizer Key | azure_form_recognizer_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Function Key | azure_function_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Azure | Azure Health Decision Support Key | azure_health_decision_support_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Health Insights Key | azure_health_insights_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Immersive Reader Key | azure_immersive_reader_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Internal All In One Key | azure_internal_all_in_one_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure IoT Device Connection String | azure_iot_device_connection_string | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure IoT Device Key | azure_iot_device_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure IoT Device Provisioning Key | azure_iot_device_provisioning_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure IoT Hub Connection String | azure_iot_hub_connection_string | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure IoT Hub Key | azure_iot_hub_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure IoT Provisioning Connection String | azure_iot_provisioning_connection_string | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Knowledge Key | azure_knowledge_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Logic Apps URL | azure_logic_apps_url, [Token versions](#token-versions) | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Azure | Azure Luis Authoring Key | azure_luis_authoring_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Luis Key | azure_luis_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Microsoft Azure Service Management Certificate | azure_management_certificate | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Maps Key | azure_maps_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Metrics Advisor Key | azure_metrics_advisor_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Mixed Reality Key | azure_mixed_reality_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure ML Inference Key | azure_ml_inference_identifiable_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure ML Internal Service Principal Key | azure_ml_internal_service_principal_identifiable_key | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Azure | Azure ML Studio (classic) Web Service Key | azure_ml_web_service_classic_identifiable_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure OpenAI Key | azure_openai_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Azure | Azure Personalizer Key | azure_personalizer_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure QnA Maker Key | azure_qna_maker_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure QnA Maker V2 Key | azure_qna_maker_v2_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Quantum Key | azure_quantum_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Relay Key Identifiable | azure_relay_key_identifiable | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure SAS Token | azure_sas_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Search Admin Key | azure_search_admin_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Search Query Key | azure_search_query_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Service Bus Key Identifiable | azure_service_bus_identifiable | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure SignalR Connection String | azure_signalr_connection_string | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure SignalR Key | azure_signalr_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Speech Services Key | azure_speech_services_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Speech Translation Key | azure_speech_translation_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure SQL Internal Default CloudSA Key | azure_sql_internal_default_cloudsa_key | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Azure | Azure SQL password | azure_sql_password | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Storage Account Access Key | azure_storage_account_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Azure | Azure Text Analytics Key | azure_text_analytics_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Text Translation Key | azure_text_translation_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Azure | Azure Video Intelligence Key | azure_video_intelligence_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Microsoft Azure Web App Bot Key | azure_web_app_bot_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Web Pub Sub Connection String | azure_web_pub_sub_connection_string | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Azure Web Pub Sub Key | azure_web_pub_sub_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Azure | Microsoft Azure Entra ID Token | microsoft_azure_entra_id_token | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Baidu | Baidu AI API Key | baiduai_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Baidu | Baidu Cloud API Access Key | baiducloud_api_accesskey | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Beamer | Beamer API Key | beamer_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Bitbucket | Bitbucket Server Personal Access Token | bitbucket_server_personal_access_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Bitrise | Bitrise Personal Access Token | bitrise_personal_access_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Bitrise | Bitrise Workspace API Token | bitrise_workspace_api_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Block Protocol | Block Protocol API Key | block_protocol_api_key | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Brevo | Sendinblue API Key | sendinblue_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Brevo | Sendinblue SMTP Key | sendinblue_smtp_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Buildkite | Buildkite Agent Access Token | buildkite_agent_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Buildkite | Buildkite Agent Job Token | buildkite_agent_job_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Buildkite | Buildkite Agent Registration Token | buildkite_agent_registration_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Buildkite | Buildkite Cluster Queue Token | buildkite_cluster_queue_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Buildkite | Buildkite Cluster Token | buildkite_cluster_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Buildkite | Buildkite Packages Registry Token | buildkite_packages_registry_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Buildkite | Buildkite Packages Temporary Token | buildkite_packages_temporary_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Buildkite | Buildkite Portal Secret | buildkite_portal_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Buildkite | Buildkite Portal Token | buildkite_portal_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Buildkite | Buildkite User Access Token | buildkite_user_access_token | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Canadian Digital Service | Canadian Digital Service Notify API Key | cds_canada_notify_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Canva | Canva App Secret | canva_app_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Canva | Canva Connect API Secret | canva_connect_api_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Canva | Canva Secret | canva_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Cashfree | Cashfree API Key | cashfree_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Cfx.re | Cfx.re Server Key | cfxre_server_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Checkout.com | Checkout.com Production Secret Key | checkout_production_secret_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Checkout.com | Checkout.com Test Secret Key | checkout_test_secret_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Chief Tools | Chief Tools Token | chief_tools_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| CircleCI | CircleCI Bot API Token | circleci_bot_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| CircleCI | CircleCI Personal Access Token | circleci_personal_access_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| CircleCI | CircleCI Project Access Token | circleci_project_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| CircleCI | CircleCI Release API Token | circleci_release_integration_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Clojars | Clojars Deploy Token | clojars_deploy_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Cloudflare | Cloudflare Account API Token | cloudflare_account_api_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Cloudflare | Cloudflare Global User API Key | cloudflare_global_user_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Cloudflare | Cloudflare User API Token | cloudflare_user_api_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Cloudsmith | Cloudsmith API Key | cloudsmith_api_key | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Cockroach Labs | CockroachDB Cloud API Key | ccdb_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Cohere | Cohere API Key | cohere_api_key | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Contentful | Contentful Personal Access Token | contentful_personal_access_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Contentful | Contentful Web Token | contentful_web_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Contributed Systems | Contributed Systems Credentials | contributed_systems_credentials | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Coveo | Coveo Access Token | coveo_access_token | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Coveo | Coveo API Key | coveo_api_key | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| crates.io | Crates.io API Token | cratesio_api_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Databento | Databento API Key | databento_api_key | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ |
| Databricks | Databricks API Token | databricks_access_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Databricks | Databricks Account Session Token | databricks_account_session_token | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Databricks | Databricks Federated Account Session Token | databricks_federated_account_session_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Databricks | Databricks OAuth Code | databricks_oauth_code | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Databricks | Databricks OAuth Refresh Token | databricks_oauth_refresh_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Databricks | Databricks OAuth Secret Token | databricks_oauth_secret_token | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Databricks | Databricks OAuth Single Use Refresh Token Child | databricks_oauth_single_use_refresh_token_child | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Databricks | Databricks OAuth Single Use Refresh Token Parent | databricks_oauth_single_use_refresh_token_parent | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Databricks | Databricks Scoped API Token | databricks_scoped_api_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Databricks | Databricks Scoped Internal Token | databricks_scoped_internal_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Databricks | Databricks Token | databricks_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Databricks | Databricks Workspace Session Token | databricks_workspace_session_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Datadog | Datadog API Key | datadog_api_key | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Datadog | Datadog Application Key | datadog_app_key, [Token versions](#token-versions) | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Datadog | Datadog Personal Access Token | datadog_pat | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Datadog | Datadog RCM | datadog_rcm | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Datadog | Datadog Service Account Token | datadog_sat | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Datastax | Datastax AstraCS Tokens | datastax_astracs_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| DeepSeek | DeepSeek API Key | deepseek_api_key | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Defined Networking | Defined Networking Managed Nebula API Key | defined_networking_nebula_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| DevCycle | DevCycle Client API Key | devcycle_client_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| DevCycle | DevCycle Mobile API Key | devcycle_mobile_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| DevCycle | DevCycle Server API Key | devcycle_server_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| DigitalOcean | DigitalOcean OAuth Token | digitalocean_oauth_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| DigitalOcean | DigitalOcean Personal Access Token | digitalocean_personal_access_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| DigitalOcean | DigitalOcean Refresh Token | digitalocean_refresh_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| DigitalOcean | DigitalOcean System Token | digitalocean_system_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Discord | Discord Bot Token | discord_bot_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Docker | Docker Organization Access Token | docker_organization_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Docker | Docker Personal Access Token | docker_personal_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Docker | Docker Swarm Join Token | docker_swarm_join_token | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Docker | Docker Swarm Unlock Key | docker_swarm_unlock_key | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Doppler | Doppler Audit Token | doppler_audit_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Doppler | Doppler CLI Token | doppler_cli_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Doppler | Doppler Personal Token | doppler_personal_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Doppler | Doppler SCIM Token | doppler_scim_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Doppler | Doppler Service Account Token | doppler_service_account_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Doppler | Doppler Service Token | doppler_service_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Dropbox | Dropbox Access Token | dropbox_access_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Dropbox | Dropbox Short-Lived Access Token | dropbox_short_lived_access_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Duffel | Duffel Live Access Token | duffel_live_access_token | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Duffel | Duffel Test Access Token | duffel_test_access_token | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Dynatrace | Dynatrace API Token | dynatrace_api_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Dynatrace | Dynatrace Internal Token | dynatrace_internal_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| EasyPost | EasyPost Production API Key | easypost_production_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| EasyPost | EasyPost Test API Key | easypost_test_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| eBay | eBay Production Client ID (App ID) | ebay_production_client_id, ebay_production_client_secret | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| eBay | eBay Sandbox Client ID (App ID) | ebay_sandbox_client_id, ebay_sandbox_client_secret | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Elastic | Elastic Cloud API Key | elastic_cloud_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Elastic | Elastic Stack API Key | elastic_stack_api_key, [Token versions](#token-versions) | ✗ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Facebook | Facebook Access Token | facebook_access_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Fastly | Fastly API Token | fastly_api_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Fieldguide | Fieldguide API Token | fieldguide_api_token | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Figma | Figma Personal Access Token | figma_pat | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Figma | Figma SCIM API Token | figma_scim_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Finicity | Finicity App Key | finicity_app_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Firebase | Firebase Cloud Messaging Server Key | firebase_cloud_messaging_server_key | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Flickr | Flickr API Key | flickr_api_key | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Flutterwave | Flutterwave Live API Secret Key | flutterwave_live_api_secret_key | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Flutterwave | Flutterwave Test API Secret Key | flutterwave_test_api_secret_key | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Frame.io | Frame.io Developer Token | frameio_developer_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Frame.io | Frame.io JSON Web Token | frameio_jwt | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| FullStory | FullStory API Key | fullstory_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| GitHub | GitHub App Installation Access Token | github_app_installation_access_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| GitHub | GitHub OAuth Access Token | github_oauth_access_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| GitHub | GitHub Personal Access Token | github_personal_access_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| GitHub | GitHub Refresh Token | github_refresh_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| GitHub | GitHub SSH Private Key | github_ssh_private_key | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| GitHub | GitHub Test Token | github_test_token | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| GitLab | GitLab Access Token | gitlab_access_token, [Token versions](#token-versions) | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| GitLab | GitLab CI/CD Job Token | gitlab_ci_build_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GitLab | GitLab Deploy Token | gitlab_deploy_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GitLab | GitLab Feature Flag Client Token | gitlab_feature_flag_client_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GitLab | GitLab Feed Token | gitlab_feed_token_v2 | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GitLab | GitLab Incoming Mail Token | gitlab_incoming_email_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GitLab | GitLab Agent for Kubernetes Token | gitlab_kubernetes_agent_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GitLab | GitLab OAuth Application Secret | gitlab_oauth_app_secret | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GitLab | GitLab Pipeline Trigger Token | gitlab_pipeline_trigger_token | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| GitLab | GitLab Runner Authentication Token | gitlab_runner_auth_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GitLab | GitLab Runner Registration Token | gitlab_runner_registration_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GitLab | GitLab SCIM Token | gitlab_scim_oauth_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GoCardless | GoCardless Live Access Token | gocardless_live_access_token | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| GoCardless | GoCardless Sandbox Access Token | gocardless_sandbox_access_token | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| Google | Google API Key | google_api_key | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ |
| Google | Google Cloud Service Account Credentials | google_cloud_service_account_credentials | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Google | Google Cloud Storage Service Account Access Key ID | google_cloud_storage_access_key_secret, google_cloud_storage_service_account_access_key_id | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Google | Google Cloud Storage User Access Key ID | google_cloud_storage_access_key_secret, google_cloud_storage_user_access_key_id | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Google | GCP API Key Bound to a Service Account | google_gcp_api_key_bound_service_account | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Google | Google Gemini API Key | google_gemini_api_key | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Google | Google OAuth Access Token | google_oauth_access_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Google | Google OAuth Client ID | google_oauth_client_id, google_oauth_client_secret, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Google | Google OAuth Refresh Token | google_oauth_refresh_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Grafana | Grafana Cloud API Key | grafana_cloud_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Grafana | Grafana Cloud API Token | grafana_cloud_api_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Grafana | Grafana Project API Key | grafana_project_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Grafana | Grafana Project Service Account Token | grafana_project_service_account_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Groq | Groq API Key | groq_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| GuardSquare | GuardSquare AppSweep API Key | guardsquare_appsweep_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GuardSquare | GuardSquare CLI Access Token | guardsquare_cli_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| GuardSquare | GuardSquare Maven Token | guardsquare_maven_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Hack Club | Hack Club AI Key | hackclub_ai_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| HashiCorp | HashiCorp Vault Batch Token | hashicorp_vault_batch_token, [Token versions](#token-versions) | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| HashiCorp | HashiCorp Vault Root Service Token | hashicorp_vault_root_service_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| HashiCorp | HashiCorp Vault Service Token | hashicorp_vault_service_token, [Token versions](#token-versions) | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| HashiCorp | Terraform Cloud / Enterprise API Token | terraform_api_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| hCaptcha | hCaptcha Siteverify Secret | hcaptcha_siteverify_secret | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Heroku | Heroku Platform API OAuth2 Token | heroku_platform_api_oauth2_token | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Heroku | Heroku Postgres Connection URL | heroku_postgres_connection_url | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Highnote | Highnote RK Live Key | highnote_rk_live_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Highnote | Highnote RK Test Key | highnote_rk_test_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Highnote | Highnote SK Live Key | highnote_sk_live_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Highnote | Highnote SK Test Key | highnote_sk_test_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| HOP | HOP Bearer | hop_bearer | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| HOP | HOP PAT | hop_pat | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| HOP | HOP PTK | hop_ptk | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Hubspot | Hubspot API Key | hubspot_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Hubspot | Hubspot Personal Access Key | hubspot_personal_access_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Hubspot | Hubspot Private Apps User Token | hubspot_private_apps_user_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Hubspot | Hubspot SMTP Credential | hubspot_smtp_credential, [Token versions](#token-versions) | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Hugging Face | Hugging Face Organization API Token | hf_org_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Hugging Face | Hugging Face User Access Token | hf_user_access_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| IBM | IBM Cloud IAM Key | ibm_cloud_iam_key | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Intercom | Intercom Access Token | intercom_access_token | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Ionic | Ionic Personal Access Token | ionic_personal_access_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Ionic | Ionic Refresh Token | ionic_refresh_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Iterative | DVC Studio Access Token | iterative_dvc_studio_access_token | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| JFrog | JFrog Platform Access Token | jfrog_platform_access_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| JFrog | JFrog Platform API Key | jfrog_platform_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| JFrog | JFrog Platform Reference Token | jfrog_platform_reference_token, [Token versions](#token-versions) | ✗ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Langchain | LangSmith Personal Access Token | langchain_api_personal_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Langchain | LangSmith Service Key | langchain_api_server_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Langchain | LangSmith License Key | langsmith_license_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Langchain | LangSmith SCIM Bearer Token | langsmith_scim_bearer_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Lark | Lark APaaS Client Secret | lark_apaas_client_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Lark | Lark Application Secret | lark_app_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Lark | Lark MCP Grant Token | lark_mcp_grant_token | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Lark | Lark Meego Plugin Secret | lark_meego_plugin_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Lark | Lark User Session | lark_user_session | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| LaunchDarkly | LaunchDarkly API Token | launchdarkly_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Lichess | Lichess OAuth Access Token | lichess_oauth_access_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Lichess | Lichess Personal Access Token | lichess_personal_access_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Lightspeed | Lightspeed Personal Access Token | lightspeed_xs_pat | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Limbar | Limbar Token | limbar_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Linear | Linear API Key | linear_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Linear | Linear OAuth Access Token | linear_oauth_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| LinkedIn | LinkedIn Client Secret | linkedin_client_secret | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Lob | Lob Live API Key | lob_live_api_key | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Lob | Lob Test API Key | lob_test_api_key | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Localstack | Localstack API Key | localstack_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| LogicMonitor | LogicMonitor Bearer Token | logicmonitor_bearer_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| LogicMonitor | LogicMonitor LMv1 Access Key | logicmonitor_lmv1_access_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Login with Amazon | Login with Amazon OAuth Client ID | amazon_oauth_client_id, amazon_oauth_client_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Lovable Labs | Lovable API Key | lovable_api_key | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mailchimp | Mailchimp API Key | mailchimp_api_key | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Mailchimp | Mandrill API Key | mandrill_api_key | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mailersend | Mailersend API Token | mailersend_api_token | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mailersend | Mailersend SMTP Password | mailersend_smtp_password | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mailersend | Mailersend SMTP Username | mailersend_smtp_username | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mailgun | Mailgun API Key | mailgun_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Mailgun | Mailgun SMTP Credential | mailgun_smtp_credential | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mapbox | Mapbox Secret Access Token | mapbox_secret_access_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| MaxMind | MaxMind License Key | maxmind_license_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Meraki | Meraki Dashboard API Key | meraki_api_key | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Mercury | Mercury Non-Production API Token | mercury_non_production_api_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Mercury | Mercury Production API Token | mercury_production_api_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Mergify | Mergify Application Key | mergify_application_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| MessageBird | MessageBird API Key | messagebird_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Microsoft | Power Automate Webhook SAS | power_automate_webhook_sas | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Midtrans | Midtrans Production Server Key | midtrans_production_server_key | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Midtrans | Midtrans Sandbox Server Key | midtrans_sandbox_server_key | ✗ | ✓ | ✗ | ✓ | ✗ | ✗ |
| Mistral AI | Mistral AI API Key | mistral_ai_api_key | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| MongoDB | MongoDB Atlas Database URI with credentials | mongodb_atlas_db_uri_with_credentials | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| MongoDB | MongoDB Atlas Service Account Secret | mongodb_atlas_service_account_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Naver Cloud | Naver Cloud Gov Access Key ID | navercloud_gov_access_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Naver Cloud | Naver Cloud Gov Secret Key | navercloud_gov_access_key_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Naver Cloud | Naver Cloud Gov Secure Token Service | navercloud_gov_sts | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Naver Cloud | Naver Cloud Gov Secure Token Service Secret | navercloud_gov_sts_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Naver Cloud | Naver Cloud Access Key ID | navercloud_pub_access_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Naver Cloud | Naver Cloud Secret Key | navercloud_pub_access_key_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Naver Cloud | Naver Cloud Secure Token Service | navercloud_pub_sts | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Naver Cloud | Naver Cloud Secure Token Service Secret | navercloud_pub_sts_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Neon | Neon API Key | neon_api_key | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Neon | Neon Connection URI | neon_connection_uri | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Netflix | Netflix NetKey | netflix_netkey | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| New Relic | New Relic Insights Query Key | new_relic_insights_query_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| New Relic | New Relic License Key | new_relic_license_key | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| New Relic | New Relic Personal API Key | new_relic_personal_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| New Relic | New Relic REST API Key | new_relic_rest_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Notion | Notion API Token | notion_api_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Notion | Notion Integration Token | notion_integration_token | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Notion | Notion OAuth Client Secret | notion_oauth_client_secret | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| npm | npm Access Token | npm_access_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| NuGet | NuGet API Key | nuget_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Octopus Deploy | Octopus Deploy API Key | octopus_deploy_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Oculus | Oculus Access Token | oculus_access_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| OneChronos | OneChronos API Token | onechronos_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| OneChronos | OneChronos Expressive Bidding API Key | onechronos_eb_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| OneChronos | OneChronos Expressive Bidding Encryption Key | onechronos_eb_encryption_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| OneChronos | OneChronos OAuth Token | onechronos_oauth_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| OneChronos | OneChronos Refresh Token | onechronos_refresh_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| OneSignal | OneSignal Rich API Key | onesignal_rich_authentication_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Onfido | Onfido Live API Token | onfido_live_api_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Onfido | Onfido Sandbox API Token | onfido_sandbox_api_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| OpenAI | OpenAI API Key | openai_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| OpenRouter | OpenRouter API Key | openrouter_api_key | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| OpenVSX | OpenVSX Access Token | openvsx_access_token, [Token versions](#token-versions) | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Openweather | Openweather API Key | openweather_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Oracle | Oracle API Key | oracle_api_key | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Orbit | Orbit API Token | orbit_api_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Paddle | Paddle API Key | paddle_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Paddle | Paddle Sandbox API Key | paddle_sandbox_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| PagerDuty | PagerDuty OAuth Secret | pagerduty_oauth_secret | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| PagerDuty | PagerDuty OAuth Token | pagerduty_oauth_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Palantir | Palantir JSON Web Token | palantir_jwt | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Pangea | Pangea Token | pangea_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Perplexity | Perplexity API Key | perplexity_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Persona Identities | Persona Production Api Key | persona_production_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Persona Identities | Persona Sandbox Api Key | persona_sandbox_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Pineapple Technologies Limited | Pineapple Technologies Incident API Key | pineapple_technologies_incident_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Pinecone | Pinecone API Key | pinecone_api_key | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Pinterest | Pinterest Access Token | pinterest_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Pinterest | Pinterest Refresh Token | pinterest_refresh_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| PlanetScale | PlanetScale Database Password | planetscale_database_password | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| PlanetScale | PlanetScale OAuth Token | planetscale_oauth_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| PlanetScale | PlanetScale Service Token | planetscale_service_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Planning Center | Planning Center OAuth Access Token | planning_center_oauth_access_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Planning Center | Planning Center OAuth Application Secret | planning_center_oauth_app_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Planning Center | Planning Center Personal Access Token | planning_center_personal_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Plivo | Plivo Auth ID | plivo_auth_id, plivo_auth_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Polar | Polar Access Token | polar_access_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Polar | Polar Authorization Code | polar_authorization_code, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Polar | Polar Client Registration Token | polar_client_registration_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Polar | Polar Client Secret | polar_client_secret, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Polar | Polar Customer Session Token | polar_customer_session_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Polar | Polar Personal Access Token | polar_personal_access_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Polar | Polar Refresh Token | polar_refresh_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Polar | Polar User Session Token | polar_user_session_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| PostHog | PostHog Feature Flags Secure API Key | posthog_feature_flags_secure_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| PostHog | PostHog OAuth Access Token | posthog_oauth_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| PostHog | PostHog OAuth Refresh Token | posthog_oauth_refresh_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| PostHog | PostHog Personal API Key | posthog_personal_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Postman | Postman API Key | postman_api_key | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Postman | Postman Collection Key | postman_collection_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Prefect | Prefect Server API Key | prefect_server_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Prefect | Prefect User API Key | prefect_user_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Proctorio | Proctorio Consumer Key | proctorio_consumer_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Proctorio | Proctorio Linkage Key | proctorio_linkage_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Proctorio | Proctorio Registration Key | proctorio_registration_key | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Proctorio | Proctorio Secret Key | proctorio_secret_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Proof | Proof Full Access API Key | proof_full_access_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Pulumi | Pulumi Access Token | pulumi_access_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| PyPI | PyPI API Token | pypi_api_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Rainforest Pay | Rainforest API Key | rainforest_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Rainforest Pay | Rainforest Sandbox API Key | rainforest_sandbox_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Ramp | Ramp OAuth Client ID | ramp_client_id | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Ramp | Ramp OAuth Client Secret | ramp_client_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Ramp | Ramp OAuth Access or Refresh Token | ramp_oauth_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Raycast | Raycast Access Token | raycast_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| ReadMe | ReadMe API Key | readmeio_api_access_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| redirect.pizza | redirect.pizza API Token | redirect_pizza_api_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Replicate | Replicate API Token | replicate_api_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Resend | Resend API Key | resend_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Rootly | Rootly API Key | rootly_api_key | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| RubyGems | RubyGems API Key | rubygems_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| RunPod | RunPod API Key | runpod_api_key | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Salesforce | Salesforce Access Token | salesforce_access_token | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Salesforce | Salesforce Marketing Cloud API OAuth2 Token | salesforce_marketing_cloud_api_oauth2_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Salesforce | Salesforce OAuth2 Consumer Key | salesforce_oauth2_consumer_key, salesforce_oauth2_consumer_secret | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Salesforce | Salesforce Refresh Token | salesforce_refresh_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Samsara | Samsara API Token | samsara_api_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Samsara | Samsara OAuth Access Token | samsara_oauth_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Scalr | Scalr API Token | scalr_api_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Segment | Segment Public API Token | segment_public_api_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| SendGrid | SendGrid API Key | sendgrid_api_key | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Sentry | Sentry Integration Token | sentry_integration_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Sentry | Sentry Organization Token | sentry_organization_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Sentry | Sentry Personal Token | sentry_personal_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Sentry | Sentry User App Auth Token | sentry_user_app_auth_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Shippo | Shippo Live API Token | shippo_live_api_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Shippo | Shippo Test API Token | shippo_test_api_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Shopee | Shopee Open Platform Partner Key | shopee_open_platform_partner_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Shopify | Shopify Access Token | shopify_access_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Shopify | Shopify App Client Credentials | shopify_app_client_credentials | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Shopify | Shopify App Client Secret | shopify_app_client_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Shopify | Shopify App Shared Secret | shopify_app_shared_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Shopify | Shopify Custom App Access Token | shopify_custom_app_access_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Shopify | Shopify Marketplace Token | shopify_marketplace_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Shopify | Shopify Merchant Token | shopify_merchant_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Shopify | Shopify Partner API Token | shopify_partner_api_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Shopify | Shopify Private App Password | shopify_private_app_password | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Siemens | Siemens API Token | siemens_api_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Siemens | Siemens Code Token | siemens_code_token | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Sindri | Sindri API Key | sindri_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Slack | Slack API Token | slack_api_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Slack | Slack Incoming Webhook URL | slack_incoming_webhook_url | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Slack | Slack Workflow Trigger URL | slack_workflow_trigger_url | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Slack | Slack Workflow Webhook URL | slack_workflow_webhook_url | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Snowflake | SFPG Connection String | snowflake_postgres_connection_string | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Snowflake | SFPG Host | snowflake_postgres_host, snowflake_postgres_password | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Snowflake | Snowflake Programmatic Access Token | snowflake_programmatic_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Sourcegraph | Sourcegraph Access Token | sourcegraph_access_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Sourcegraph | Sourcegraph Dotcom User Gateway Access Token | sourcegraph_dotcom_user_gateway | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Sourcegraph | Sourcegraph Access Token with Instance Identifier | sourcegraph_instance_identifier_access_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Sourcegraph | Sourcegraph License Key Token | sourcegraph_license_key_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Sourcegraph | Sourcegraph Product Subscription Token | sourcegraph_product_subscription_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Square | Square Access Token | square_access_token, [Token versions](#token-versions) | ✗ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Square | Square Production Application Secret | square_production_application_secret | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Square | Square Sandbox Application Secret | square_sandbox_application_secret | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| SSLMate | SSLMate API Key | sslmate_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| SSLMate | SSLMate Cluster Secret | sslmate_cluster_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Stripe | Stripe API Key | stripe_api_key | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Stripe | Stripe Legacy API Key | stripe_legacy_api_key | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Stripe | Stripe Live API Restricted Key | stripe_live_restricted_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Stripe | Stripe Test API Restricted Key | stripe_test_restricted_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Stripe | Stripe Test API Secret Key | stripe_test_secret_key | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Stripe | Stripe Webhook Signing Secret | stripe_webhook_signing_secret | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Supabase | Supabase OAuth Access Token | supabase_oauth_access_token | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Supabase | Supabase Personal Access Token | supabase_personal_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Supabase | Supabase Personal Access Token (scoped) | supabase_scoped_personal_access_token | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Supabase | Supabase Secret Key | supabase_secret_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Tableau | Tableau Personal Access Token | tableau_personal_access_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Tailscale | Tailscale API Key | tailscale_api_key | ✓ | ✓ | ✗ | ✓ | ✓ | ✗ |
| Telegram | Telegram Bot Token | telegram_bot_token | ✗ | ✓ | ✗ | ✓ | ✓ | ✗ |
| Telnyx | Telnyx API V2 Key | telnyx_api_v2_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Temporal | Temporal Cloud API Key | temporal_cloud_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Tencent | Tencent Cloud International Access Token | tencent_cloud_intl_access_token | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Tencent | Tencent Cloud Secret ID | tencent_cloud_secret_id | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Tencent | Tencent WeChat API App ID | tencent_wechat_api_app_id | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Tencent | Tencent WeChat Pay Token | tencent_wechat_pay_token | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Thunderstore | Thunderstore IO API Token | thunderstore_io_api_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Twilio | Twilio Access Token | twilio_access_token | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Twilio | Twilio Account String Identifier | twilio_account_sid, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Twilio | Twilio API Key | twilio_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Typeform | Typeform Personal Access Token | typeform_personal_access_token | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Uniwise | WISEflow API Key | wiseflow_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Unkey | Unkey Root Key | unkey_root_key | ✓ | ✓ | ✗ | ✓ | ✗ | ✗ |
| Val Town | Val Town API Token | val_town_api_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Vercel | Vercel API Key | vercel_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Vercel | Vercel App Refresh Token | vercel_app_refresh_token | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| Vercel | Vercel App User Access Token | vercel_app_user_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Vercel | Vercel Integration Access Token | vercel_integration_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Vercel | Vercel Personal Access Token | vercel_personal_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Vercel | Vercel Support Access Token | vercel_support_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| VolcEngine | VolcEngine Access Key ID | volcengine_access_key_id | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| VolcEngine | VolcEngine Ark API Key | volcengine_ark_api_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Wakatime | WakaTime API Key | wakatime_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Wakatime | WakaTime App Secret | wakatime_app_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Wakatime | WakaTime OAuth Access Token | wakatime_oauth_access_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Wakatime | WakaTime OAuth Refresh Token | wakatime_oauth_refresh_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Weatherstack | Weatherstack API Key | weatherstack_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Weights & Biases | Weights & Biases API Key | wandb_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Workato | Workato Developer API Token | workato_developer_api_token, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| WorkOS | WorkOS Production API Key | workos_production_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| WorkOS | WorkOS Staging API Key | workos_staging_api_key, [Token versions](#token-versions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| WSO2 | WSO2 Choreo Personal Access Token | wso2_choreo_personal_access_token | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| xAI | xAI API Key | xai_api_key | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Yandex | Yandex.Cloud API Key | yandex_cloud_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Yandex | Yandex.Cloud Access Secret | yandex_cloud_iam_access_secret | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Yandex | Yandex.Cloud IAM Cookie | yandex_cloud_iam_cookie | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Yandex | Yandex.Cloud IAM Token | yandex_cloud_iam_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Yandex | Yandex.Cloud Smartchapta Server Key | yandex_cloud_smartcaptcha_server_key | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Yandex | Yandex.Dictionary API Key | yandex_dictionary_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Yandex | Yandex.Passport OAuth Token | yandex_passport_oauth_token | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Yandex | Yandex.Predictor API Key | yandex_predictor_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Yandex | Yandex.Translate API Key | yandex_translate_api_key | ✗ | ✓ | ✓ | ✓ | ✗ | ✗ |
| ZenHub | ZenHub Personal API Key | zenhub_personal_api_key | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Zuplo | Zuplo Consumer API Key | zuplo_consumer_api_key | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
