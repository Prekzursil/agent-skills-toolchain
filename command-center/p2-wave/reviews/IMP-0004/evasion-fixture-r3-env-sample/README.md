IMP-0004 r3 novel evasion fixture (SYNTHETIC ONLY).
Method: env_sample — plant synthetic credential in a `.env.sample`-shaped dotenv file.
Tip fixes for base64_wrapped_* and split_literal_* do not specially settle this path;
content scan must still block via github_token / assigned_secret.
