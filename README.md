# ZenSuggest AI Indexer

This repository contains an Azure Function that indexes Zendesk tickets into a Supabase database for use with the ZenSuggest AI application. The function is automatically deployed to Azure via GitHub Actions when changes are pushed to the master branch.

## Overview

The ZenSuggest AI Indexer is an Azure Function that runs on an hourly schedule to:

1. Fetch tickets from Zendesk using the Zendesk API
2. Process and chunk the ticket content
3. Generate embeddings for each chunk using OpenAI
4. Store the chunks and embeddings in Supabase for retrieval by the ZenSuggest AI application

## Architecture

- **Azure Function**: Timer-triggered function that runs hourly
- **GitHub Actions**: Automated CI/CD pipeline for deployment to Azure
- **Zendesk API**: Source of ticket data
- **OpenAI API**: Used for generating embeddings
- **Supabase**: Vector database for storing ticket chunks and embeddings

## Setup

### Prerequisites

- Azure Function App set up in Azure
- Zendesk account with API access
- OpenAI API key
- Supabase project with the appropriate tables (see schema below)

### Environment Variables

Copy the `.env_example` file to `.env` for local development:

```bash
cp .env_example .env
```

Required environment variables (must be configured in Azure Function App settings for production):

- `ZENDESK_SUBDOMAIN`: Your Zendesk subdomain
- `ZENDESK_EMAIL`: Your Zendesk email
- `ZENDESK_API_TOKEN`: Your Zendesk API token
- `OPENAI_API_KEY`: Your OpenAI API key
- `LLM_MODEL`: The OpenAI model to use (e.g., gpt-4o-mini)
- `SUPABASE_URL`: Your Supabase URL
- `SUPABASE_SERVICE_KEY`: Your Supabase service key

### Local Development

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Install Azure Functions Core Tools to run the function locally.

3. Run the function locally:

```bash
func start
```

## Dependency Management in Azure Functions

This project includes a special approach to dependency management to address issues with Azure Functions not properly installing dependencies from requirements.txt.

The `install_dependencies.py` script in the `ZendeskTicketIndexer` directory installs dependencies to the `.python_packages` directory, which is where Azure Functions looks for packages when running in the cloud.

To run this script manually:

```bash
cd ZendeskTicketIndexer
python install_dependencies.py
```

The Azure Function's `__init__.py` file includes code to add the `.python_packages` directory to the Python path, ensuring that dependencies are properly loaded.

## Deployment

### Automatic Deployment

This repository includes a GitHub Actions workflow that automatically deploys the Azure Function to Azure when changes are pushed to the master branch. The workflow is defined in `.github/workflows/master_zendeskticketindexer.yml`.

### Manual Deployment

To deploy manually:

1. Zip the function app:

```bash
zip -r function_deploy.zip ./*
```

2. Deploy using Azure Functions Core Tools:

```bash
func azure functionapp publish ZendeskTicketIndexer --zip function_deploy.zip
```

## Supabase Schema

The function expects a table named `zendesk_tickets` in Supabase with the following schema:

```sql
CREATE TABLE zendesk_tickets (
  id BIGSERIAL PRIMARY KEY,
  url TEXT NOT NULL,
  chunk_number INTEGER NOT NULL,
  title TEXT NOT NULL,
  summary TEXT,
  content TEXT NOT NULL,
  metadata JSONB,
  embedding VECTOR(1536)
);

-- Create a function to match documents by embedding similarity
CREATE OR REPLACE FUNCTION match_zendesk_tickets(
  query_embedding VECTOR(1536),
  match_count INT DEFAULT 5,
  filter JSONB DEFAULT '{}'
) RETURNS TABLE (
  id BIGINT,
  url TEXT,
  chunk_number INTEGER,
  title TEXT,
  summary TEXT,
  content TEXT,
  metadata JSONB,
  similarity FLOAT
) LANGUAGE plpgsql AS $$
BEGIN
  RETURN QUERY
  SELECT
    zendesk_tickets.id,
    zendesk_tickets.url,
    zendesk_tickets.chunk_number,
    zendesk_tickets.title,
    zendesk_tickets.summary,
    zendesk_tickets.content,
    zendesk_tickets.metadata,
    1 - (zendesk_tickets.embedding <=> query_embedding) AS similarity
  FROM zendesk_tickets
  WHERE CASE
    WHEN filter->>'source' IS NOT NULL THEN
      metadata->>'source' = filter->>'source'
    ELSE
      TRUE
    END
  ORDER BY zendesk_tickets.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
```

## Monitoring and Troubleshooting

### Logs

The function includes comprehensive logging. You can view logs in the Azure Portal under the Function App's "Logs" section.

### Common Issues

If you encounter issues with dependencies not being found when the function runs in Azure:

1. Check the function logs to see which dependencies are missing
2. Run the `install_dependencies.py` script locally
3. Zip the entire function directory, including the `.python_packages` directory
4. Deploy the zip file to Azure

## License

This project is proprietary and confidential.
