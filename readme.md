# 🎓 Skillsbucket RAG — Proposal Assistant

An advanced, AI-powered corporate training assistant built using a **Retrieval-Augmented Generation (RAG)** pipeline. This application facilitates corporate sales and training consultants by providing instant, verified details about training programs, commercial pricing policies, and terms, and automating the creation of high-quality, customized client proposals.

---

## 📸 Application Screenshots

### 💬 Chat Assistant
<p align="center">
  <img src="Project_img/Screenshot%202026-06-29%20185053.png" width="49%" alt="Chat Assistant Interface" />
  <img src="Project_img/Screenshot%202026-06-29%20185105.png" width="49%" alt="Active Conversation with Sources" />
</p>

### 📄 Proposal Generator
<p align="center">
  <img src="Project_img/Screenshot%202026-06-29%20185121.png" width="49%" alt="Proposal Intake Form & Options" />
  <img src="Project_img/Screenshot%202026-06-29%20185136.png" width="49%" alt="Generated Markdown Proposal" />
</p>
<p align="center">
  <img src="Project_img/Screenshot%202026-06-29%20185206.png" width="60%" alt="Word Document Export & Form Preview" />
</p>

---

## 🛠️ The Dual System Architecture

The application is split into two distinct, powerful modules depending on the consultant's objective:

### 1. 💬 Chat Assistant (Closed-Book Q&A)
*   **Purpose**: Provides instant answers regarding course modules, pricing models, payment terms, or company information.
*   **Key Behavior**: Strictly closed-book. It retrieves relevant knowledge fragments using semantic search from ChromaDB. If a query is off-topic (e.g., general knowledge, math, history), the assistant politely refuses to answer.
*   **Information Richness**: Displays matching sources and content categories (e.g., Leadership, Terms & Conditions) below each response.

### 2. 📄 Proposal Generator (Automated Proposal Maker)
*   **Purpose**: Automatically draft comprehensive, client-ready business proposals tailored to client requirements.
*   **Intake Details**: The sidebar form collects client name, target industry, course name, delivery mode, participant count, duration, preferred dates, and specific client requirements.
*   **Key Behavior**: Combines intake details with course curriculum details, company qualifications, commercial policies, and T&Cs retrieved from ChromaDB to draft a formal proposal.
*   **Export Ready**: The proposal is rendered in a premium document style and can be downloaded as a Microsoft Word (`.docx`) file with a single click.

---

## 🔄 Project Workflow

The following flowchart illustrates the ingestion pipeline and the runtime RAG architecture:

```mermaid
graph TD
    %% Ingestion Pipeline
    subgraph Ingestion Phase (Run Once)
        JSON[Raw JSON Data<br>output/ folder] -->|1. Read & Parse| Ingest[ingest.py]
        Ingest -->|2. Chunking & Metadata tagging| HF[HuggingFace Embeddings<br>all-MiniLM-L6-v2]
        HF -->|3. Store Vectors| Chroma[Chroma DB<br>./chroma_db]
    end

    %% Application Server & Client
    subgraph Run-Time Execution (Dual-System)
        User[Consultant / User] -->|4. Input details & Interact| Streamlit[Streamlit Frontend<br>interface.py]
        Streamlit -->|5a. Ask Question| ChatAPI[FastAPI /chat API]
        Streamlit -->|5b. Generate Proposal| PropAPI[FastAPI /proposal API]
        
        ChatAPI -->|6. Search Query| Chroma
        PropAPI -->|6. Retrieve Context| Chroma
        
        Chroma -.->|7. Context chunks| LLM[LLM Provider<br>Mistral / Gemini]
        LLM -->|8. Generate Response| Streamlit
        Streamlit -->|9. Export Word Doc| DOCX[DOCX Download]
    end

    classDef phase fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff;
    classDef client fill:#0f172a,stroke:#10b981,stroke-width:2px,color:#fff;
    class JSON,Ingest,HF,Chroma phase;
    class User,Streamlit,ChatAPI,PropAPI,LLM,DOCX client;
```

---

## 📂 Project Folder Structure

```
skillsbucket_rag/
│
├── ingest.py                              ← Ingestion: Run once to process JSON files to Vector DB
├── app_api.py                             ← Backend: FastAPI endpoints (/chat, /proposal, /stats)
├── interface.py                           ← Frontend: Streamlit client application
├── requirements.txt                       ← Dependencies (FastAPI, Streamlit, ChromaDB, etc.)
├── .env.template                          ← Environment template
├── .env                                   ← API keys & Configuration (locally created)
│
├── Project_img/                           ← UI Screenshots for documentation
│   ├── Screenshot 2026-06-29 185053.png
│   ├── Screenshot 2026-06-29 185105.png
│   ├── Screenshot 2026-06-29 185121.png
│   ├── Screenshot 2026-06-29 185136.png
│   └── Screenshot 2026-06-29 185206.png
│
├── prompts/                               ← LLM Prompt Templates
│   ├── proposal_system_prompt.txt         ← Detailed proposal generation context
│   └── chat_guardrail_prompt.txt          ← RAG chatbot guardrail prompt
│
├── chroma_db/                             ← Persistent Chroma Database folder
│
└── output/                                ← Verified Skillsbucket JSON Data Store
    ├── about_skillsbucket/                ← Company Profile (about_us.json)
    ├── commercial/                        ← Pricing models & Policies (pricing_policy.json)
    ├── company/                           ← Contact & Location details (contact.json)
    ├── terms_and_conditions/              ← Legal T&Cs (terms_and_conditions.json)
    ├── Services/                          ← Specialized Services
    └── courses_detail/                    ← Comprehensive course curricula databases
```

---

## 🚀 Setup & Installation Instructions

### 1. Prerequisites & Dependencies
Ensure you have Python 3.9+ installed. Run the following command to install the required libraries:
```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.template` to a new file named `.env`:
```bash
cp .env.template .env
```
Open `.env` and fill in your API key for your chosen provider:
```ini
LLM_PROVIDER=gemini # Or 'mistral'
GOOGLE_API_KEY=AIzaSy...
MISTRAL_API_KEY=your_mistral_key_here
```

### 3. Build Vector Knowledge Base
Build the vector database by running the ingestion script (only needed when raw JSON databases in `output/` are added or updated):
```bash
python ingest.py
```
This script reads all JSON files in `output/`, fragments them into clean text blocks, extracts metadata, computes embeddings, and stores them in the `./chroma_db` folder.

### 4. Start the FastAPI API Server
Start the backend server in a separate terminal:
```bash
uvicorn app_api:app --reload --port 8000
```
Verify the API is running by checking health stats: http://localhost:8000/stats

### 5. Launch the Streamlit Web Application
In another terminal, start the user interface:
```bash
streamlit run interface.py
```
The application will open automatically in your browser at: **http://localhost:8501**

---

## 💡 Usage Guidelines

### 💬 Utilizing the Chat Assistant
Simply enter your question in the chat input. The system will retrieve relevant chunks from the knowledge base and respond.
*   **Sample Queries**:
    *   *"What is the syllabus for Leadership Skills for First Time Managers?"*
    *   *"What are the pricing rules for a virtual (VILT) 2-day session with 25 attendees?"*
    *   *"Tell me about Skillsbucket's experience, methodology, and background."*
*   **Guardrails**: If you ask *"What is the distance to the moon?"* or *"Who won the 2022 World Cup?"*, the system will politely decline, ensuring maximum compliance with Skillsbucket information.

### 📄 Utilizing the Proposal Generator
1.  Complete the client details and program requirements in the left sidebar.
2.  Navigate to the **Generate Proposal** tab.
3.  Click the **Generate Full Proposal** button.
4.  Once generated, you can review the proposal directly in the app.
5.  Click **Download Proposal (.docx)** to download a formatted Microsoft Word document ready to send to the client.

---

## 🔧 Troubleshooting

*   **Error: "Collection not found"**:
    *   *Solution*: Make sure to run `python ingest.py` first to populate the vector database.
*   **Streamlit displays "API Offline"**:
    *   *Solution*: Ensure the FastAPI server is running on port 8000 using the `uvicorn` command.
*   **Low Quality Proposal Output**:
    *   *Solution*: Ensure you have provided sufficient curriculum details and company information inside the `output/` JSON directories. Re-run `python ingest.py` after adding any files.