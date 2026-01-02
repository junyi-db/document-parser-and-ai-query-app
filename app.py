import streamlit as st
import pandas as pd
import os
import json
import time
from databricks.sdk import WorkspaceClient
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from config import Config

# Load environment variables from .env file
load_dotenv()

# Configure Streamlit page
st.set_page_config(
    page_title="Document Parser with Databricks AI",
    page_icon="📄",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Style for HTML tables from parsed documents */
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 10px 0;
        font-size: 14px;
    }
    table th, table td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: left;
    }
    table th {
        background-color: #f2f2f2;
        font-weight: bold;
    }
    table tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    table tr:hover {
        background-color: #f5f5f5;
    }
    
    /* Step indicators */
    .step-header {
        background: linear-gradient(90deg, #1976d2 0%, #42a5f5 100%);
        color: white;
        padding: 10px 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    
    /* File card styling */
    .file-card {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 15px;
        border-left: 4px solid #1976d2;
    }
    
    /* Upload hint box */
    .upload-hint {
        text-align: center;
        padding: 40px;
        background-color: #f0f2f6;
        border-radius: 10px;
        margin: 20px 0;
        border: 2px dashed #ccc;
    }
    
    /* Primary button enhancement */
    .stButton > button[kind="primary"] {
        font-size: 16px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

def init_databricks_client() -> Optional[WorkspaceClient]:
    """Initialize Databricks workspace client with credentials."""
    try:
        # Try to create client - will use environment variables or .databrickscfg
        client = WorkspaceClient()
        return client
    except Exception as e:
        st.error(f"Failed to initialize Databricks client: {str(e)}")
        st.info("""
        Please configure Databricks credentials using one of these methods:
        1. Set environment variables: DATABRICKS_HOST, DATABRICKS_TOKEN
        2. Use .databrickscfg file in your home directory
        3. Use Azure CLI authentication (for Azure Databricks)
        """)
        return None

def upload_file_to_dbfs(client: WorkspaceClient, file_bytes: bytes, filename: str) -> Optional[str]:
    """Upload file to DBFS and return the path."""
    try:
        # Validate input
        if not file_bytes:
            raise ValueError("No file content provided")
        
        if not isinstance(file_bytes, bytes):
            raise ValueError(f"Expected bytes, got {type(file_bytes)}")
        
        # Create a temporary file path in DBFS
        dbfs_path = f"/tmp/document_parser/{filename}"
        
        # Upload file to DBFS using BytesIO
        from io import BytesIO
        file_io = BytesIO(file_bytes)
        
        # Upload to DBFS (pass the file object, not file path)
        client.dbfs.upload(dbfs_path, file_io, overwrite=True)
            
        return dbfs_path
    except Exception as e:
        st.error(f"Failed to upload file to DBFS: {str(e)}")
        return None

def get_warehouse_id() -> Optional[str]:
    """Get warehouse ID from user input or environment variables."""
    # First, try to get from user input in session state
    user_warehouse_id = st.session_state.get('warehouse_id', '').strip()
    if user_warehouse_id:
        return user_warehouse_id
    
    # Fall back to environment variable
    return Config.DEFAULT_WAREHOUSE_ID

def parse_ai_response(content: str) -> Dict[str, Any]:
    """
    Parse the AI document response into a structured format.
    Handles various response formats from Databricks ai_parse_document.
    """
    result = {
        'is_json': False,
        'elements': [],
        'raw_content': content,
        'plain_text': '',
        'tables': [],
        'figures': [],
        'headers': [],
        'metadata': {}
    }
    
    if not content:
        return result
    
    # Try to parse as JSON
    try:
        # Handle string that might be JSON
        if isinstance(content, str):
            # Try direct JSON parse
            parsed = json.loads(content)
        else:
            parsed = content
            
        result['is_json'] = True
        
        # Handle different response structures
        elements = []
        
        # Structure 1: {"document": {"elements": [...]}}
        if isinstance(parsed, dict):
            if 'document' in parsed and isinstance(parsed['document'], dict):
                elements = parsed['document'].get('elements', [])
                result['metadata'] = {k: v for k, v in parsed['document'].items() if k != 'elements'}
            # Structure 2: {"elements": [...]}
            elif 'elements' in parsed:
                elements = parsed.get('elements', [])
                result['metadata'] = {k: v for k, v in parsed.items() if k != 'elements'}
            # Structure 3: Direct content or other format
            elif 'content' in parsed:
                result['plain_text'] = str(parsed.get('content', ''))
            elif 'text' in parsed:
                result['plain_text'] = str(parsed.get('text', ''))
            else:
                # Store the whole parsed object
                result['metadata'] = parsed
        # Structure 4: Direct array of elements
        elif isinstance(parsed, list):
            elements = parsed
        
        # Process elements
        plain_text_parts = []
        for elem in elements:
            if not isinstance(elem, dict):
                continue
                
            elem_type = elem.get('type', 'unknown').lower()
            elem_content = elem.get('content', '')
            elem_description = elem.get('description', '')
            
            processed_elem = {
                'type': elem_type,
                'content': elem_content,
                'description': elem_description,
                'id': elem.get('id'),
                'page_id': elem.get('page_id', elem.get('bbox', [{}])[0].get('page_id') if isinstance(elem.get('bbox'), list) else None),
                'bbox': elem.get('bbox', elem.get('coord')),
                'raw': elem
            }
            
            result['elements'].append(processed_elem)
            
            # Categorize by type
            if elem_type in ['table', 'tables']:
                result['tables'].append(processed_elem)
            elif elem_type in ['figure', 'image', 'picture', 'chart', 'diagram']:
                result['figures'].append(processed_elem)
            elif elem_type in ['header', 'page_header', 'title', 'heading', 'section_header']:
                result['headers'].append(processed_elem)
            
            # Build plain text
            if elem_content:
                plain_text_parts.append(str(elem_content))
            elif elem_description:
                plain_text_parts.append(f"[{elem_type}: {elem_description}]")
        
        result['plain_text'] = '\n\n'.join(plain_text_parts)
        
    except (json.JSONDecodeError, TypeError, AttributeError):
        # Not JSON, treat as plain text
        result['plain_text'] = str(content)
    
    return result

def render_element_content(element: Dict[str, Any], key_prefix: str = ""):
    """Render a single document element based on its type."""
    elem_type = element.get('type', 'unknown').lower()
    content = element.get('content', '')
    description = element.get('description', '')
    page_id = element.get('page_id')
    
    # Page indicator
    page_info = f" (Page {page_id + 1})" if page_id is not None else ""
    
    if elem_type in ['table', 'tables']:
        st.markdown(f"**📊 Table{page_info}**")
        if content:
            # Try to render HTML table
            if '<table' in str(content).lower():
                st.markdown(content, unsafe_allow_html=True)
            else:
                st.code(content, language=None)
        if description:
            st.caption(f"Description: {description}")
            
    elif elem_type in ['figure', 'image', 'picture', 'chart', 'diagram']:
        st.markdown(f"**🖼️ Figure{page_info}**")
        if description:
            st.info(f"📝 {description}")
        if content:
            st.text(content)
            
    elif elem_type in ['header', 'page_header', 'title', 'heading', 'section_header']:
        st.markdown(f"### 📑 {content}{page_info}")
        if description:
            st.caption(description)
            
    elif elem_type in ['text', 'paragraph', 'body']:
        if content:
            st.markdown(f"{content}")
        if description and not content:
            st.text(description)
            
    elif elem_type in ['list', 'list_item', 'bullet']:
        if content:
            st.markdown(f"• {content}")
            
    elif elem_type in ['footer', 'page_footer']:
        st.caption(f"📄 Footer{page_info}: {content or description}")
        
    else:
        # Generic handler for unknown types
        if content or description:
            st.markdown(f"**{elem_type.title()}{page_info}:**")
            if content:
                st.text(content)
            if description:
                st.caption(description)

def display_parsed_content(parsed_content: str, file_key: str):
    """Display parsed content with intelligent formatting based on response structure."""
    
    # Parse the content
    parsed = parse_ai_response(parsed_content)
    
    # Create view tabs
    view_tab1, view_tab2, view_tab3, view_tab4 = st.tabs([
        "📋 Structured View", 
        "📝 Plain Text", 
        "🔍 Raw JSON",
        "📊 Summary"
    ])
    
    with view_tab1:
        if parsed['is_json'] and parsed['elements']:
            # Group elements by page if possible
            elements_by_page = {}
            no_page_elements = []
            
            for elem in parsed['elements']:
                page_id = elem.get('page_id')
                if page_id is not None:
                    if page_id not in elements_by_page:
                        elements_by_page[page_id] = []
                    elements_by_page[page_id].append(elem)
                else:
                    no_page_elements.append(elem)
            
            # Display by page using containers instead of expanders (to avoid nesting issues)
            if elements_by_page:
                # Page selector
                page_ids = sorted(elements_by_page.keys())
                if len(page_ids) > 1:
                    selected_page = st.selectbox(
                        "Select Page",
                        options=page_ids,
                        format_func=lambda x: f"Page {x + 1}",
                        key=f"page_select_{file_key}"
                    )
                    st.markdown(f"### 📄 Page {selected_page + 1}")
                    st.markdown("---")
                    for i, elem in enumerate(elements_by_page[selected_page]):
                        render_element_content(elem, f"{file_key}_p{selected_page}_{i}")
                        st.markdown("---")
                else:
                    # Single page - show directly
                    page_id = page_ids[0]
                    st.markdown(f"### 📄 Page {page_id + 1}")
                    st.markdown("---")
                    for i, elem in enumerate(elements_by_page[page_id]):
                        render_element_content(elem, f"{file_key}_p{page_id}_{i}")
                        st.markdown("---")
            
            # Display elements without page info
            if no_page_elements:
                st.markdown("### 📄 Document Content")
                st.markdown("---")
                for i, elem in enumerate(no_page_elements):
                    render_element_content(elem, f"{file_key}_nop_{i}")
                    st.markdown("---")
        else:
            # Fall back to plain text display
            st.markdown("*No structured elements found. Showing plain text:*")
            st.text_area(
                "Content",
                value=parsed['plain_text'] or parsed['raw_content'],
                height=400,
                key=f"structured_{file_key}"
            )
    
    with view_tab2:
        plain_text = parsed['plain_text'] or parsed['raw_content']
        st.text_area(
            "Extracted Text",
            value=plain_text,
            height=400,
            key=f"plain_{file_key}"
        )
        
        # Download as text
        st.download_button(
            label="📥 Download as Text",
            data=plain_text,
            file_name=f"parsed_{file_key}.txt",
            mime="text/plain",
            key=f"download_txt_{file_key}"
        )
    
    with view_tab3:
        if parsed['is_json']:
            try:
                # Pretty print JSON
                formatted_json = json.dumps(json.loads(parsed['raw_content']), indent=2)
                st.code(formatted_json, language="json")
            except:
                st.code(parsed['raw_content'], language="json")
        else:
            st.info("Content is not in JSON format")
            st.code(parsed['raw_content'])
        
        # Download as JSON
        st.download_button(
            label="📥 Download as JSON",
            data=parsed['raw_content'],
            file_name=f"parsed_{file_key}.json",
            mime="application/json",
            key=f"download_json_{file_key}"
        )
    
    with view_tab4:
        st.markdown("### 📊 Document Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Elements", len(parsed['elements']))
        with col2:
            st.metric("Tables", len(parsed['tables']))
        with col3:
            st.metric("Figures", len(parsed['figures']))
        with col4:
            st.metric("Headers", len(parsed['headers']))
        
        # Element type breakdown
        if parsed['elements']:
            st.markdown("#### Element Types")
            type_counts = {}
            for elem in parsed['elements']:
                elem_type = elem.get('type', 'unknown')
                type_counts[elem_type] = type_counts.get(elem_type, 0) + 1
            
            # Create a simple bar display
            for elem_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
                st.write(f"**{elem_type}:** {count}")
        
        # Metadata if available
        if parsed['metadata']:
            st.markdown("#### 📋 Metadata")
            st.json(parsed['metadata'])
        
        # Tables preview - use container instead of expander
        if parsed['tables']:
            st.markdown("#### 📊 Tables Found")
            table_select = st.selectbox(
                "Select Table to Preview",
                options=range(len(parsed['tables'])),
                format_func=lambda x: f"Table {x + 1}",
                key=f"table_select_{file_key}"
            )
            content = parsed['tables'][table_select].get('content', '')
            if '<table' in str(content).lower():
                st.markdown(content, unsafe_allow_html=True)
            else:
                st.code(content)
        
        # Figures preview
        if parsed['figures']:
            st.markdown("#### 🖼️ Figures Found")
            for i, fig in enumerate(parsed['figures']):
                desc = fig.get('description', 'No description')
                st.write(f"**Figure {i + 1}:** {desc}")

def parse_document_with_ai(client: WorkspaceClient, dbfs_path: str) -> Optional[Dict[str, Any]]:
    """Parse document using Databricks AI parse function."""
    try:
        # Create a SQL query to parse the document
        sql_query = f"""
        SELECT
            path,
            ai_parse_document(content) as parsed_content
        FROM READ_FILES('{dbfs_path}', format => 'binaryFile')
        """
        
        # Execute the query using Databricks SQL
        # Note: This requires a SQL warehouse or cluster to be running
        result = client.statement_execution.execute_statement(
            warehouse_id=get_warehouse_id(),
            statement=sql_query,
            wait_timeout="30s"
        )
        
        if result.result and result.result.data_array:
            # Parse the result
            parsed_data = {
                'path': result.result.data_array[0][0] if result.result.data_array[0] else dbfs_path,
                'parsed_content': result.result.data_array[0][1] if len(result.result.data_array[0]) > 1 else None
            }
            return parsed_data
        
        return None
        
    except Exception as e:
        st.error(f"Failed to parse document: {str(e)}")
        return None

def execute_agent_query(client: WorkspaceClient, table_name: str, input_column: str, 
                        prompt: str, output_column: str) -> Optional[pd.DataFrame]:
    """Execute AI query using Foundation Models."""
    try:
        warehouse_id = get_warehouse_id()
        if not warehouse_id:
            st.error("❌ No warehouse ID available. Please configure DATABRICKS_WAREHOUSE_ID environment variable or enter it in the sidebar.")
            return None
            
        # Create the SQL query
        sql_query = f"""
        SELECT
          {input_column},
          ai_query(
            'databricks-gpt-5-2',
            CONCAT('{prompt}', {input_column})
          ) AS {output_column}
        FROM {table_name}
        LIMIT 100;
        """
        
        st.info(f"🔄 Executing AI query on warehouse: {warehouse_id}")
        
        # Execute the query
        result = client.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            statement=sql_query,
            wait_timeout="50s"  # Maximum allowed timeout for AI queries
        )
        
        # Check for execution errors
        if hasattr(result, 'status') and result.status:
            if result.status.state == "FAILED":
                error_msg = "Query execution failed"
                if hasattr(result.status, 'error') and result.status.error:
                    error_msg += f": {result.status.error.message if hasattr(result.status.error, 'message') else str(result.status.error)}"
                st.error(f"❌ {error_msg}")
                return None
        
        if result.result and result.result.data_array:
            # Convert to DataFrame
            columns = [input_column, output_column]
            data = result.result.data_array
            df = pd.DataFrame(data, columns=columns)
            return df
        else:
            st.error("❌ No data returned from query. Check if the table exists and the endpoint is accessible.")
            return None
            
    except Exception as e:
        error_type = type(e).__name__
        st.error(f"❌ Failed to execute AI query ({error_type}): {str(e)}")
        
        # Provide specific guidance
        if "endpoint" in str(e).lower():
            st.error("💡 **Endpoint Issue**: Check if the Foundation Model endpoint 'databricks-gpt-5-2' exists and is running.")
        elif "table" in str(e).lower():
            st.error("💡 **Table Issue**: Verify the table name and that you have access to it.")
        elif "permission" in str(e).lower() or "access" in str(e).lower():
            st.error("💡 **Permission Issue**: Check if you have access to the table and model endpoint.")
        elif "timeout" in str(e).lower():
            st.error("💡 **Timeout Issue**: AI queries can take longer. Try with fewer rows or check endpoint performance.")
            
        return None

def render_sidebar():
    """Render the configuration sidebar."""
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Databricks warehouse ID
        default_warehouse_hint = f" (Default: {Config.DEFAULT_WAREHOUSE_ID})" if Config.DEFAULT_WAREHOUSE_ID else ""
        warehouse_id = st.text_input(
            f"Databricks SQL Warehouse ID{default_warehouse_hint}",
            value=st.session_state.get('warehouse_id', ''),
            help="Enter your Databricks SQL Warehouse ID for executing queries. Leave empty to use the default warehouse from environment variables."
        )
        
        if warehouse_id:
            st.session_state['warehouse_id'] = warehouse_id
        
        # Show current warehouse being used
        current_warehouse = get_warehouse_id()
        if current_warehouse:
            if st.session_state.get('warehouse_id', '').strip():
                st.success(f"✅ Using warehouse: {current_warehouse}")
            else:
                st.info(f"ℹ️ Using default warehouse: {current_warehouse}")
        else:
            st.warning("⚠️ No warehouse configured")
        
        st.markdown("---")
        st.markdown("""
        **Available Features:**
        - 📄 Document Parser: Parse PDFs and images
        - 🤖 Agent Query: Use AI endpoints on table data
        """)

def document_parser_tab(client):
    """Document parser functionality."""
    
    # Step 1: Upload Section
    st.markdown("### Step 1️⃣ Upload Your Document")
    st.markdown("Select PDF, PNG, JPG, or JPEG files to parse using Databricks ai_parse_document function.")
    
    uploaded_files = st.file_uploader(
        "Choose files to parse",
        accept_multiple_files=True,
        type=['pdf', 'png', 'jpg', 'jpeg'],
        help="Upload one or more documents to parse with Databricks AI",
        key="doc_uploader"
    )
    
    if uploaded_files:
        st.markdown("---")
        
        # Step 2: Parse Section - Make it very clear
        st.markdown("### Step 2️⃣ Parse Your Documents")
        
        # Show uploaded files summary
        st.info(f"📁 **{len(uploaded_files)} file(s) uploaded** and ready to parse")
        
        # File cards with parse buttons
        for uploaded_file in uploaded_files:
            file_key = uploaded_file.name.replace('.', '_').replace(' ', '_')
            
            # Create a card-like container for each file
            with st.container():
                st.markdown(f"""
                <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 15px; border-left: 4px solid #1976d2;">
                    <strong>📄 {uploaded_file.name}</strong><br>
                    <small style="color: #666;">Size: {uploaded_file.size / 1024:.2f} KB | Type: {uploaded_file.type}</small>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    # Big, prominent Parse button
                    parse_clicked = st.button(
                        f"🚀 Parse Document",
                        key=f"parse_{file_key}",
                        type="primary",
                        use_container_width=True
                    )
                
                # Check session state for parsed results
                result_key = f"parsed_result_{file_key}"
                
                if parse_clicked:
                    with st.spinner(f"🔄 Processing {uploaded_file.name}..."):
                        try:
                            # Read file bytes
                            uploaded_file.seek(0)
                            file_bytes = uploaded_file.read()
                            
                            if not file_bytes:
                                st.error("❌ Failed to read file content")
                            else:
                                # Upload and parse with status updates
                                with st.status("Processing document...", expanded=True) as status:
                                    st.write("⬆️ Uploading file to DBFS...")
                                    dbfs_path = upload_file_to_dbfs(client, file_bytes, uploaded_file.name)
                                    
                                    if dbfs_path:
                                        st.write("🤖 Parsing document with AI...")
                                        parsed_result = parse_document_with_ai(client, dbfs_path)
                                        
                                        if parsed_result and parsed_result.get('parsed_content'):
                                            st.write("✅ Document parsed successfully!")
                                            status.update(label="✅ Parsing complete!", state="complete")
                                            st.session_state[result_key] = parsed_result['parsed_content']
                                        else:
                                            status.update(label="❌ Parsing failed", state="error")
                                            st.error("Failed to parse document or no content extracted.")
                                    else:
                                        status.update(label="❌ Upload failed", state="error")
                                        st.error("Failed to upload file to DBFS.")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                
                # Display results if available
                if result_key in st.session_state:
                    st.markdown("---")
                    st.markdown("### 📊 Parsing Results")
                    display_parsed_content(
                        str(st.session_state[result_key]),
                        file_key
                    )
                
                st.markdown("---")
    
    else:
        # No files uploaded - show clear instructions
        st.markdown("---")
        st.markdown("""
        <div style="text-align: center; padding: 40px; background-color: #f0f2f6; border-radius: 10px; margin: 20px 0;">
            <h3>👆 Upload a document to get started</h3>
            <p style="color: #666;">Drag and drop files or click "Browse files" above</p>
            <p><strong>Supported formats:</strong> PDF, PNG, JPG, JPEG</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Instructions section at bottom
    with st.expander("📖 How to Use", expanded=False):
        st.markdown("""
        ### Quick Guide:
        
        1. **Upload** - Drag and drop or browse for files (PDF, PNG, JPG, JPEG)
        2. **Parse** - Click the blue "🚀 Parse Document" button for each file
        3. **View** - Explore results in Structured View, Plain Text, or JSON format
        4. **Download** - Export parsed content in your preferred format
        
        ### Tips:
        - Ensure your Databricks credentials are configured in the sidebar
        - Larger documents may take longer to process
        - Tables and figures are automatically detected and displayed
        """)

def agent_query_tab(client):
    """Agent query functionality using Foundation Model endpoint."""
    st.header("🤖 AI Agent Query")
    st.markdown("Execute AI queries on table data using the Foundation Model endpoint 'databricks-gpt-5-2'.")
    
    # Query configuration
    col1, col2 = st.columns(2)
    
    with col1:
        table_name = st.text_input(
            "Table Name",
            placeholder="catalog.schema.table_name",
            help="Enter the full table name (catalog.schema.table)"
        )
        
        input_column = st.text_input(
            "Input Column",
            placeholder="text_column",
            help="Name of the column containing the text to process"
        )
    
    with col2:
        output_column = st.text_input(
            "Output Column",
            value="ai_response",
            help="Name for the output column that will contain AI responses"
        )
        
        prompt = st.text_area(
            "Prompt",
            placeholder="Summarize the following text: ",
            help="The prompt to prepend to each input text",
            height=100
        )
    
    # Query preview
    if table_name and input_column and output_column and prompt:
        st.subheader("📝 Query Preview")
        query_preview = f"""
        SELECT
          {input_column},
          ai_query(
            'databricks-gpt-5-2',
            CONCAT('{prompt}', {input_column})
          ) AS {output_column}
        FROM {table_name}
        LIMIT 100;
        """
        st.code(query_preview, language="sql")
        
        # Execute button
        if st.button("🚀 Execute AI Query", type="primary"):
            with st.spinner("Executing AI query..."):
                result_df = execute_agent_query(
                    client, table_name, input_column, prompt, output_column
                )
                
                if result_df is not None:
                    st.success(f"✅ Query executed successfully! Retrieved {len(result_df)} rows.")
                    
                    # Display results
                    st.subheader("📊 Query Results")
                    st.dataframe(result_df, use_container_width=True)
                    
                    # Download button
                    csv = result_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Results as CSV",
                        data=csv,
                        file_name=f"ai_query_results_{output_column}.csv",
                        mime="text/csv"
                    )
    else:
        st.info("Please fill in all fields to see the query preview and execute.")
    
    # Example section
    with st.expander("💡 Example Usage", expanded=False):
        st.markdown("""
        ### Example Configuration:
        
        **Table Name:** `main.default.customer_feedback`  
        **Input Column:** `feedback_text`  
        **Output Column:** `sentiment_analysis`  
        **Prompt:** `Analyze the sentiment of the following customer feedback and classify it as positive, negative, or neutral: `
        
        This would create a query that analyzes customer feedback sentiment using the AI endpoint.
        
        ### Tips:
        - Make sure the table exists and you have read access
        - The input column should contain text data
        - Keep prompts clear and specific for better results
        - The endpoint 'databricks-gpt-5-2' must be running and accessible
        """)

def main():
    st.title("🏢 Databricks AI Platform")
    st.markdown("A comprehensive platform for document parsing and AI agent queries using Databricks.")
    
    # Render sidebar
    render_sidebar()
    
    # Initialize Databricks client
    client = init_databricks_client()
    
    if not client:
        st.stop()
    
    if not get_warehouse_id():
        st.warning("Please configure your Databricks SQL Warehouse ID in the sidebar or set the DATABRICKS_WAREHOUSE_ID environment variable to proceed.")
        st.stop()
    
    # Create tabs
    tab1, tab2 = st.tabs(["📄 Document Parser", "🤖 Agent Query"])
    
    with tab1:
        document_parser_tab(client)
    
    with tab2:
        agent_query_tab(client)

if __name__ == "__main__":
    main()