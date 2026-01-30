import streamlit as st
import pandas as pd
import google.generativeai as genai
import os

# --- 1. 설정 및 API 연결 ---
try:
    api_key = st.secrets["GEMINI_API_KEY"]
    gsheet_url = st.secrets["GSHEET_URL"]
except:
    api_key = ""
    gsheet_url = ""

if api_key:
    # API 버전을 명시적으로 설정하여 404 오류를 방지합니다.
    genai.configure(api_key=api_key)

# --- 2. 구글 시트 로드 함수 (데이터 깨짐 방지) ---
def load_gsheet_data(url):
    if not url: return ""
    try:
        # CSV 내보내기 링크 생성
        csv_url = url.replace('/edit#gid=', '/export?format=csv&gid=') if "edit" in url else url
        if "export?format=csv" not in csv_url:
            csv_url = csv_url.rstrip('/') + '/export?format=csv'
        
        # 데이터 구조가 깨진 행(bad lines)을 무시하고 로드하여 오류를 방지합니다.
        df = pd.read_csv(csv_url, on_bad_lines='skip', engine='python')
        return df.to_string(index=False)
    except Exception as e:
        st.error(f"구글 시트를 읽는 데 실패했습니다: {e}")
        return ""

# --- 3. UI 및 데이터 로드 ---
st.title("🤖 사내 규정 안내 챗봇 (시트 전용)")
knowledge_base = load_gsheet_data(gsheet_url)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- 4. 질문 처리 ---
if prompt := st.chat_input("질문을 입력하세요."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            # [해결책] 404 에러 방지를 위해 'models/'를 명시적으로 붙여 호출합니다.
            model = genai.GenerativeModel(model_name='models/gemini-1.5-flash')
            
            # [cite_start]입력 토큰 한도(429 에러)를 넘지 않도록 텍스트를 제한합니다[cite: 1, 2, 3].
            safe_context = knowledge_base[:50000] 
            
            full_query = f"아래 지식 베이스를 참고하여 답변해줘.\n\n[지식 베이스]\n{safe_context}\n\n질문: {prompt}"
            
            response = model.generate_content(full_query)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})
            
        except Exception as e:
            # 여전히 404가 날 경우를 대비해 대안 모델(gemini-pro)로 즉시 재시도합니다.
            if "404" in str(e):
                try:
                    model_alt = genai.GenerativeModel(model_name='models/gemini-pro')
                    response = model_alt.generate_content(full_query)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e2:
                    st.error(f"⚠️ 모델 호출 실패: {e2}")
            elif "429" in str(e):
                st.error("⚠️ 너무 많은 요청이 들어왔습니다. 1분 뒤에 다시 시도해 주세요.")
            else:
                st.error(f"⚠️ 오류 발생: {e}")


