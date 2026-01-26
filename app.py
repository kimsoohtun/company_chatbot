import streamlit as st
import pandas as pd
import pdfplumber
from docx import Document
import google.generativeai as genai


# --- 관리자 설정 (Secrets에서 불러오기) ---
# 로컬 테스트 시에는 '기본값'을 사용하고, 배포 후에는 Secrets를 사용합니다.
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    gsheet_url = st.secrets["GSHEET_URL"]
    genai.configure(api_key=api_key)
except:
    st.warning("관리자 설정을 불러올 수 없습니다. (로컬 테스트 중이신가요?)")
    api_key = ""
    gsheet_url = ""


# --- UI 수정: 사이드바 숨기기 ---
# 이제 직원들에게는 아무것도 보여줄 필요가 없으므로 사이드바 기능을 제거하거나 간소화합니다.
st.title("🤖 사내 규정 안내 챗봇")
st.info("안녕하세요! 무엇이 궁금하신가요? (연차, 경조사, 전산자원 운용 등)")
st.set_page_config(page_title="사내 규정 챗봇", layout="wide")


# --- 2. 텍스트 추출 로직 ---
def extract_text(files, g_url):
    text_data = ""
    sources = []
    for f in files:
        content = ""
        if f.name.endswith('.pdf'):
            with pdfplumber.open(f) as pdf:
                content = "\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
        elif f.name.endswith('.docx'):
            content = "\n".join([p.text for p in Document(f).paragraphs])
        elif f.name.endswith('.xlsx'):
            content = pd.read_excel(f).to_string()
        text_data += f"\n\n[출처: {f.name}]\n{content}"
        sources.append(f.name)
    
    if g_url:
        try:
            csv_url = g_url.replace('/edit#gid=', '/export?format=csv&gid=') if "edit" in g_url else g_url
            df = pd.read_csv(csv_url)
            text_data += f"\n\n[출처: 구글 시트]\n{df.to_string()}"
            sources.append("구글 시트")
        except: pass
    return text_data, sources

# --- 3. 채팅 엔진 ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# 지식 구축
knowledge_base, source_list = extract_text(uploaded_files, gsheet_url)

# 대화 출력
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 질문 처리
if prompt := st.chat_input("질문을 입력하세요"):
    if not api_key:
        st.error("API 키가 필요합니다.")
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                # 리스트에 있는 모델 중 하나를 선택 (Gemini 2.5 Flash 권장)
                model = genai.GenerativeModel('gemini-2.5-flash')
                
                # 변수명을 full_query로 통일하여 에러 방지
                full_query = f"""너는 사내 규정 전문가야. 다음 지식을 바탕으로 답변해줘.
                답변 끝에 참고한 문서명을 적어줘. 모르면 '인사팀 문의'라고 해.
                
                [지식 베이스]
                {knowledge_base}
                
                질문: {prompt}"""
                
                response = model.generate_content(full_query)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:

                st.error(f"오류 발생: {e}")
