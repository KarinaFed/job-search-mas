"""Script to create .env file from env.example."""
import shutil
import os

def create_env_file():
    """Create .env file from env.example if it doesn't exist."""
    if os.path.exists('.env'):
        print(".env file already exists. Skipping creation.")
        return
    
    if os.path.exists('env.example'):
        shutil.copy('env.example', '.env')
        print("Created .env file from env.example")
    else:
        print("env.example not found. Creating default .env file...")
        with open('.env', 'w') as f:
            f.write("""# LiteLLM Configuration
LITELLM_BASE_URL=http://a6k2.dgx:34000/v1
LITELLM_API_KEY=your_api_key
MODEL_NAME=qwen3-32b

# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=job_search_mas
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# HH.ru API
# Option 1: OAuth2 (recommended for production)
HH_CLIENT_ID=your_hh_client_id
HH_CLIENT_SECRET=your_hh_client_secret

# Option 2: Direct access token (legacy)
HH_API_KEY=

# API URL
HH_API_URL=https://api.hh.ru

# Application
APP_ENV=development
LOG_LEVEL=INFO
""")
        print("Created default .env file")

if __name__ == "__main__":
    create_env_file()

