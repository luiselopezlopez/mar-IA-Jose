<# Set secrets in the container app
az containerapp secret set `
    --name mariajoseai `
    --resource-group mariajoseai `
    --secrets `
        "api-key=1ngB5JL78uwzx2hG5ZMAPixEhIHBfXCntNGydPnb4yuI3NDsnKvdJQQJ99BCACHYHv6XJ3w3AAAAACOG7BsL" `
        "model-name=gpt-4" `
        "api-version=2025-01-01-preview" `
        "azure-endpoint=https://luise-m7souxdp-eastus2.openai.azure.com" `
        "embedding-endpoint=https://librechatluise4633087029.openai.azure.com" `
        "embedding-deployment=text-embedding-ada-002" `
        "embedding-api=2023-05-15" `
        "embedding-api-key=6D93ytgxlMky6L6vOlX5XIvDNiCgptkQ5ceQ8No1z8oMZSPICAwQJQQJ99BCACYeBjFXJ3w3AAAAACOG4MQB"
#>
# Set environment variables referencing the secrets
az containerapp update `
    --name mariajoseai `
    --resource-group mariajoseai `
    --set-env-vars `
    "api_key=1ngB5JL78uwzx2hG5ZMAPixEhIHBfXCntNGydPnb4yuI3NDsnKvdJQQJ99BCACHYHv6XJ3w3AAAAACOG7BsL" `
    "model_name=gpt-4" `
    "api_version=2025-01-01-preview" `
    "azure_endpoint=https://luise-m7souxdp-eastus2.openai.azure.com" `
    "embedding_endpoint=https://librechatluise4633087029.openai.azure.com" `
    "embedding_deployment=text-embedding-ada-002" `
    "embedding_api=2023-05-15" `
    "embedding_api_key=6D93ytgxlMky6L6vOlX5XIvDNiCgptkQ5ceQ8No1z8oMZSPICAwQJQQJ99BCACYeBjFXJ3w3AAAAACOG4MQB"