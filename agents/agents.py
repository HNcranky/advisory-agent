from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from state import AdvisoryState

# Initialize your LLM (Using Gemini as an example, but you can swap to any)
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

# ---------------------------------------------------------
# 1. Profile Agent: Extracts structured data from user query
# ---------------------------------------------------------
def profile_agent(state: AdvisoryState):
    print("--- [Agent] Extracting User Profile ---")
    
    parser = JsonOutputParser()
    prompt = PromptTemplate(
        template="""Extract the following information from the user's university admission query.
        Return ONLY a JSON object with keys: 'mock_score' (float or null), 'desired_major' (string or null), 'target_university' (string or null).
        Query: {query}""",
        input_variables=["query"],
    )
    
    chain = prompt | llm | parser
    # If the LLM fails to parse, we provide a safe fallback
    try:
        extracted_profile = chain.invoke({"query": state["user_query"]})
    except Exception:
        extracted_profile = {"mock_score": None, "desired_major": None, "target_university": None}
        
    return {"user_profile": extracted_profile}

# ---------------------------------------------------------
# 2. Retrieval Agent: Fetches data based on the profile
# ---------------------------------------------------------
def retrieval_agent(state: AdvisoryState):
    print("--- [Agent] Retrieving Admission Data ---")
    profile = state["user_profile"]
    
    # MOCK RETRIEVAL - Replace this with actual VectorDB or Neo4j Cypher query
    mock_db_results = []
    if profile.get("desired_major") in ["IT", "CNTT", "Khoa học máy tính"]:
        mock_db_results.append("Đại học Bách khoa Hà Nội (HUST): Ngành IT1 năm 2024 điểm chuẩn là 28.53, tổ hợp A00, A01.")
        mock_db_results.append("Đại học Công nghệ (VNU-UET): Ngành CNTT năm 2024 điểm chuẩn là 27.8.")
    else:
        mock_db_results.append("Hiện tại chưa có thông tin khớp với yêu cầu của bạn.")
        
    return {"retrieved_context": mock_db_results}

# ---------------------------------------------------------
# 3. Reasoning Agent: Matches profile with retrieved data
# ---------------------------------------------------------
def reasoning_agent(state: AdvisoryState):
    print("--- [Agent] Reasoning & Analyzing Risk ---")
    
    prompt = PromptTemplate(
        template="""You are an expert admission counselor.
        User Profile: {profile}
        Admission Data: {context}
        
        Analyze the student's chances. Be realistic. If their score is lower than last year's data, warn them of the high risk.
        Output a detailed analytical paragraph.""",
        input_variables=["profile", "context"],
    )
    
    chain = prompt | llm | StrOutputParser()
    analysis = chain.invoke({
        "profile": str(state["user_profile"]),
        "context": "\n".join(state["retrieved_context"])
    })
    
    return {"reasoning_analysis": analysis}

# ---------------------------------------------------------
# 4. Policy Agent: Enforces rules (e.g., adding disclaimers)
# ---------------------------------------------------------
def policy_agent(state: AdvisoryState):
    print("--- [Agent] Enforcing Policy & Safety ---")
    analysis = state["reasoning_analysis"]
    
    # Simple rule-based policy check
    policy_status = "Passed"
    enforced_text = analysis
    
    disclaimer = "\n\n*Lưu ý từ hệ thống: Đây là dữ liệu tham khảo dựa trên điểm chuẩn các năm trước. Thông tin chính thức vui lòng theo dõi Đề án tuyển sinh 2025.*"
    
    if "Lưu ý từ hệ thống" not in enforced_text:
        enforced_text += disclaimer
        policy_status = "Appended Disclaimer"
        
    return {"policy_check_status": policy_status, "reasoning_analysis": enforced_text}

# ---------------------------------------------------------
# 5. Explanation Agent: Formats the final friendly response
# ---------------------------------------------------------
def explanation_agent(state: AdvisoryState):
    print("--- [Agent] Generating Final Explanation ---")
    
    prompt = PromptTemplate(
        template="""You are a friendly, empathetic admission consultant for Vietnamese students.
        Translate this raw analysis into a warm, encouraging, and easy-to-read response. Use bullet points if necessary.
        
        Raw Analysis: {analysis}""",
        input_variables=["analysis"],
    )
    
    chain = prompt | llm | StrOutputParser()
    final_output = chain.invoke({"analysis": state["reasoning_analysis"]})
    
    return {"final_response": final_output}