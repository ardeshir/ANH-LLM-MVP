#!/bin/bash
# scripts/deploy.sh
# MVP Deployment Script

set -e

echo "🚀 Starting MVP Deployment..."

# Check prerequisites
command -v az >/dev/null 2>&1 || { echo "Azure CLI required but not installed.  Aborting." >&2; exit 1; }
command -v python >/dev/null 2>&1 || { echo "Python required but not installed.  Aborting." >&2; exit 1; }

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
else
    echo "❌ .env file not found"
    exit 1
fi

# Azure login check
az account show >/dev/null 2>&1 || { echo "Please run 'az login' first"; exit 1; }

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "🏗️  Provisioning infrastructure..."
python infrastructure/provision_resources.py \
    --subscription $AZURE_SUBSCRIPTION_ID \
    --resource-group $RESOURCE_GROUP \
    --location $AZURE_LOCATION

echo "🔍 Creating search indexes..."
python -c "
from search.index_manager import SpeciesIndexManager, Species
manager = SpeciesIndexManager('$SEARCH_ENDPOINT')
manager.create_species_index(Species.POULTRY)
manager.create_species_index(Species.SWINE)
print('✅ Indexes created')
"

echo "⚡ Deploying Function App..."
cd functions
func azure functionapp publish $FUNCTION_APP_NAME --python
cd ..

echo "🌐 Deploying API..."
# Deploy API (example using App Service or Container)
# Adjust based on your deployment target

echo "✅ Deployment complete!"
echo ""
echo "📋 Next Steps:"
echo "1. Configure managed identity permissions in Azure Portal"
echo "2. Deploy OpenAI models (text-embedding-3-large, gpt-4o)"
echo "3. Test API endpoint: $FUNCTION_APP_URL/api/health"
echo "4. Review Application Insights dashboard"
