# Databricks AI Platform

A comprehensive Streamlit application for document parsing and AI agent queries using Databricks AI capabilities.

## Features

### 📄 Document Parser
- 📄 Support for multiple file formats (PDF, PNG, JPG, JPEG)
- 🤖 AI-powered document parsing using Databricks `ai_parse_document`
- 📁 Batch file processing
- 💾 Download parsed content as text files

### 🤖 Agent Query
- 🚀 Execute AI queries on table data using Databricks Foundation Model endpoints
- 🔄 Customizable model endpoint (supports any Databricks Foundation Model)
- 📊 Interactive query builder with real-time preview
- 💡 Custom prompt configuration for various AI tasks
- 📥 Export results to CSV format
- 🔧 Easy configuration through intuitive UI

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Databricks Credentials

Choose one of the following methods:

#### Option A: Environment Variables
```bash
export DATABRICKS_HOST="https://your-databricks-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="your-access-token"
export DATABRICKS_WAREHOUSE_ID="your-warehouse-id"  # Optional
```

#### Option B: Configuration File
Create a `.databrickscfg` file in your home directory:
```ini
[DEFAULT]
host = https://your-databricks-workspace.cloud.databricks.com
token = your-access-token
```

### 3. Get SQL Warehouse ID

1. Go to your Databricks workspace
2. Navigate to **SQL → Warehouses**
3. Copy the Warehouse ID from your desired warehouse
4. Enter it in the app's sidebar or set the `DATABRICKS_WAREHOUSE_ID` environment variable

## Usage

### 1. Start the Application

```bash
streamlit run app.py
```

### 2. Configure Settings

- Enter your Databricks SQL Warehouse ID in the sidebar (optional if `DATABRICKS_WAREHOUSE_ID` environment variable is set)
- Verify that your Databricks credentials are configured

### 3. Use the Application

#### Document Parser Tab
1. Click "Choose files to parse" to upload documents
2. Select one or more files (PDF, PNG, JPG, JPEG)
3. Click the "Parse" button for each file
4. View the extracted content
5. Download the parsed text if needed

#### Agent Query Tab
1. Enter your table name (e.g., `catalog.schema.table_name`)
2. Specify the input column containing text data
3. Set an output column name for AI responses
4. Write your prompt (e.g., "Summarize the following text:")
5. Preview the generated SQL query
6. Click "Execute AI Query" to run the query
7. View and download results as CSV

## File Support

- **PDF Documents**: Extract text, tables, and document structure
- **PNG Images**: OCR text extraction from images
- **JPG/JPEG Images**: OCR text extraction from images

## How It Works

### Document Parser
The document parser uses Databricks' `ai_parse_document` function:

1. **File Upload**: Files are uploaded to DBFS (Databricks File System)
2. **AI Processing**: The `ai_parse_document` function processes the binary content
3. **Result Display**: Extracted text and structure are displayed in the UI
4. **Download**: Users can download the parsed content as text files

### Agent Query
The agent query feature uses Foundation Model endpoints with `ai_query`:

1. **Query Building**: Users configure table, columns, and prompts through the UI
2. **SQL Generation**: The app generates optimized SQL queries with `ai_query`
3. **Endpoint Processing**: The query calls your configured Foundation Model endpoint (default: `databricks-gpt-5-2`)
4. **Results Display**: Processed data is displayed in an interactive table
5. **Export**: Results can be downloaded as CSV files

### Backend Implementation

#### Document Parser Pattern:
```python
# Upload file to DBFS
client.dbfs.upload(dbfs_path, file_content, overwrite=True)

# Execute AI parsing query
sql_query = """
SELECT
    path,
    ai_parse_document(content) as parsed_content
FROM READ_FILES('{dbfs_path}', format => 'binaryFile')
"""
```

#### Agent Query Pattern:
```python
# Execute AI query on table data
# Note: Replace 'databricks-gpt-5-2' with your preferred Foundation Model endpoint
sql_query = """
SELECT
  {input_column},
  ai_query(
    'databricks-gpt-5-2',
    CONCAT('{prompt}', {input_column})
  ) AS {output_column}
FROM {table_name}
LIMIT 100;
"""
```

## Configuration

Edit `config.py` to customize:

- Maximum file size limits
- Supported file types
- DBFS upload paths
- Default warehouse settings

### Customizing the Foundation Model Endpoint

The Agent Query feature uses Databricks Foundation Models via the `ai_query` function. By default, it uses `databricks-gpt-5-2`, but you can modify this to use any available Foundation Model endpoint.

#### Option 1: Edit the Code (app.py)

Search for `databricks-gpt-5-2` in `app.py` and replace it with your preferred endpoint:

```python
# Find this in the execute_agent_query function and agent_query_tab function:
ai_query(
    'databricks-gpt-5-2',  # Change this to your endpoint
    CONCAT('{prompt}', {input_column})
)
```

#### Option 2: Available Databricks Foundation Model Endpoints

You can use any of the following Databricks Foundation Model endpoints:

| Endpoint Name | Model | Use Case |
|--------------|-------|----------|
| `databricks-meta-llama-3-3-70b-instruct` | Llama 3.3 70B | General purpose, instruction following |
| `databricks-meta-llama-3-1-405b-instruct` | Llama 3.1 405B | Complex reasoning, high quality |
| `databricks-meta-llama-3-1-70b-instruct` | Llama 3.1 70B | Balanced performance |
| `databricks-dbrx-instruct` | DBRX | Databricks native model |
| `databricks-mixtral-8x7b-instruct` | Mixtral 8x7B | Fast, efficient |
| `databricks-mpt-30b-instruct` | MPT 30B | Instruction following |

#### Option 3: Using External Model Serving Endpoints

If you have deployed your own model serving endpoint, use its name:

```python
ai_query(
    'your-custom-endpoint-name',  # Your deployed endpoint
    CONCAT('{prompt}', {input_column})
)
```

#### Finding Available Endpoints

1. Go to your Databricks workspace
2. Navigate to **Serving** in the left sidebar
3. View the list of available endpoints
4. Copy the endpoint name (not the full URL)

#### Example: Using Claude or GPT via External Endpoints

If you've set up an external model endpoint (e.g., via Databricks Model Serving with external models):

```sql
SELECT
  text_column,
  ai_query(
    'my-claude-endpoint',
    CONCAT('Summarize: ', text_column)
  ) AS summary
FROM my_table
LIMIT 10;
```

> **Note**: Ensure your SQL warehouse has access to the Foundation Models feature and your endpoint is running before executing queries.

## Troubleshooting

### Common Issues

1. **"Failed to initialize Databricks client"**
   - Verify your credentials are set correctly
   - Check network connectivity to Databricks

2. **"Please configure your Databricks SQL Warehouse ID"**
   - Ensure you have an active SQL warehouse
   - Copy the correct Warehouse ID from the Databricks UI or set the `DATABRICKS_WAREHOUSE_ID` environment variable

3. **"Failed to parse document"**
   - Check if the warehouse is running
   - Verify the file format is supported
   - Ensure you have necessary permissions

### Requirements

- Active Databricks workspace
- SQL Warehouse or cluster with `ai_parse_document` function support
- Valid Databricks access token with appropriate permissions

## License

This project is provided as-is for demonstration purposes.