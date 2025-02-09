from dotenv import load_dotenv
import os

from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_astradb import AstraDBVectorStore
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain.tools.retriever import create_retriever_tool
from langchain_core.prompts import ChatPromptTemplate
from github import fetch_github_issues
from note import note_tool

load_dotenv()

def connect_to_vector_store(): 
    embeddings = OllamaEmbeddings(model="nomic-embed-text")  # Specify the Ollama embeddings
    ASTRA_DB_API_ENDPOINT = os.getenv("ASTRA_DB_API_ENDPOINT")
    ASTRA_DB_APPLICATION_TOKEN = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    desired_namespace = os.getenv("ASTRA_DB_KEYSPACE")

    if desired_namespace:
        ASTRA_DB_KEYSPACE = desired_namespace
    else:
        ASTRA_DB_KEYSPACE = None  # Set to None if no namespace is found

    # Initialize Astra DB vector store with namespaces (not collections)
    vstore = AstraDBVectorStore(
        embedding=embeddings,
        collection_name="gitbuddy",  # You can still set a collection name for organization purposes
        api_endpoint=ASTRA_DB_API_ENDPOINT,
        token=ASTRA_DB_APPLICATION_TOKEN,
        namespace=ASTRA_DB_KEYSPACE  # Ensure you're passing the correct namespace
    )

    return vstore

# Connect to the vector store
vstore = connect_to_vector_store()

# Ask whether to update issues from GitHub
add_to_vectorstore = input("Do you want to update the issues? (y/N): ").lower() in ["yes", "y"]

# If user chooses to update, fetch issues and add to the vector store
if add_to_vectorstore:
    owner = "tarishigeetey"
    repo = "muzik"
    issues = fetch_github_issues(owner, repo)

    try: 
        # If collection exists, delete and recreate it (optional step, may need adjustment depending on use case)
        vstore.delete_collection()
    except:
        pass

    # Add documents to the vector store
    vstore = connect_to_vector_store()
    vstore.add_documents(issues)

retriever = vstore.as_retriever(search_kwargs={"k": 3})
retriever_tool = create_retriever_tool(
    retriever,
    "github_search",
    "Search for information about GitHub issues. For any questions about GitHub issues, you can use this tool"
)

# Define role prompt
role_prompt = "Given the app name and additional context, search for related GitHub issues and provide useful insights."

# Create ChatPromptTemplate
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", role_prompt),
        ("human", "What is {input}?"),
        ("placeholder", "{agent_scratchpad}"),
    ]
)

# Define LLM and tools
llm = ChatOllama(model="llama3.2:latest")
tools = [retriever_tool, note_tool]

# Create the agent using the updated prompt
agent = create_tool_calling_agent(llm, tools, prompt)

# Define AgentExecutor
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# Main loop
while (question := input("Ask a question about GitHub issues (q to quit): ")) != "q":
    result = agent_executor.invoke({"input": question, "agent_scratchpad": ""})
    print(result["output"])
