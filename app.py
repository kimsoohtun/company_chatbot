import streamlit as st
import pandas as pd
import google.generativeai as genai

# --- 1. 설정 및 API 연결 ---
try:
    # Streamlit Secrets에서 API 키와 구글 시트 URL을 가져옵니다.
    api_key = st.secrets["GEMINI_API_KEY"]
    gsheet_url = st.secrets["GSHEET_URL"]
except Exception:
    api_key = ""
    gsheet_url = ""

if api_key:
    genai.configure(api_key=api_key)

# --- 2. 구글 시트 데이터 로드 함수 (오류 방지) ---
def load_gsheet_data(url):
    if not url:
        return "데이터가 설정되지 않았습니다."
    try:
        # 구글 시트 URL을 CSV 내보내기 형식으로 변환
        csv_url = url.replace('/edit#gid=', '/export?format=csv&gid=') if "edit" in url else url
        if "export?format=csv" not in csv_url:
            csv_url = csv_url.rstrip('/') + '/export?format=csv'
            
        # 형식이 깨진 행(Bad lines)을 건너뛰어 시트 읽기 오류를 방지합니다.
        df = pd.read_csv(csv_url, on_bad_lines='skip', engine='python')
        return df.to_string(index=False)
    except Exception as e:
        return f"데이터를 불러오는 중 오류가 발생했습니다: {e}"

# --- 3. UI 구성 ---
st.set_page_config(page_title="사내 규정 챗봇", layout="centered")
st.title("🤖 사내 규정 안내 챗봇 (시트 기반)")
st.info("현재 구글 시트에 등록된 최신 데이터를 바탕으로 답변합니다.")

# 지식 베이스 구축 (구글 시트만 읽음)
knowledge_base = load_gsheet_data(gsheet_url)

if "messages" not in st.session_state:
    st.session_state.messages = []

# 기존 대화 표시
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 4. 질문 처리 ---
if prompt := st.chat_input("궁금한 사내 규정을 물어보세요."):
    # 사용자 메시지 기록
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # [cite_start]404 오류 해결: 모델 경로를 명시적으로 호출합니다. [cite: 1]
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # [cite_start]429 오류 해결: 토큰 한도를 넘지 않게 지식 베이스를 자릅니다. [cite: 3]
            # [cite_start]한글 기준 약 50,000자 내외가 무료 티어에서 가장 안정적입니다. [cite: 2]
            safe_context = knowledge_base[:50000] 
            
            full_query = f"""너는 사내 규정 전문가야. 아래 [지식 베이스]의 내용만 참고해서 답변해줘.
만약 지식 베이스에 없는 내용이라면 '해당 내용은 인사팀에 문의하세요'라고 답변해.

[지식 베이스]
{safe_context}

질문: {prompt}"""
            
            # [cite_start]AI 답변 생성 [cite: 4]
            response = model.generate_content(full_query)
            
            if response.text:
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            # [cite_start]429(할당량 초과) 발생 시 별도 안내 [cite: 5]
            if "429" in str(e):
                [cite_start]st.error("⚠️ 한꺼번에 너무 많은 질문이 들어왔습니다. 약 1분 뒤에 다시 시도해 주세요. [cite: 5]")
            else:
                st.error(f"⚠️ 오류가 발생했습니다: {e}")
