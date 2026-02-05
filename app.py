import os
import streamlit as st
from openai import OpenAI
from docx import Document
from io import BytesIO
import fitz  # PyMuPDF

# --- НАСТРОЙКА ---
st.set_page_config(page_title="Аудитор 🧛", layout="wide", page_icon="🧛")

def extract_text(file):
    try:
        if file.name.endswith('.pdf'):
            doc = fitz.open(stream=file.read(), filetype="pdf")
            return "".join([f"\n[СТРАНИЦА {i+1}]\n{p.get_text()}" for i, p in enumerate(doc)])
        else:
            doc = Document(file)
            return "".join([f"[Абзац {i+1}] {p.text}\n" for i, p in enumerate(doc.paragraphs) if p.text.strip()])
    except Exception as e:
        st.error(f"Ошибка чтения файла: {e}")
        return ""

def load_bad_history():
    if os.path.exists("bad_history.txt"):
        try:
            with open("bad_history.txt", "r", encoding="utf-8") as f:
                return f.read()
        except:
            return "База прошлых отказов пуста."
    return "База прошлых отказов пуста."

def create_docx(text):
    doc = Document()
    doc.add_heading('ПРОТОКОЛ НЕСООТВЕТСТВИЙ', 0)
    for line in text.split('\n'):
        doc.add_paragraph(line)
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf

# --- ИНТЕРФЕЙС ---
with st.sidebar:
    st.header("⚙️ Настройки")
    selected_model = st.selectbox(
        "Выберите модель:", 
        ("deepseek-chat", "deepseek-reasoner"),
        help="Reasoner (R1) — идеален для поиска скрытых несоответствий."
    )

st.title("🧛 Симулятор Вредного Заказчика")
st.markdown("### Глубокий аудит: 3 слоя проверки")

col1, col2 = st.columns(2)
with col1:
    contract_file = st.file_uploader("📄 КОНТРАКТ", type=['pdf', 'docx'])
with col2:
    report_file = st.file_uploader("📝 ОТЧЕТ", type=['pdf', 'docx'])

if st.button("🚀 ЗАПУСТИТЬ ТОТАЛЬНЫЙ АУДИТ"):
    if contract_file and report_file:
        try:
            api_key = st.secrets.get("DEEPSEEK_API_KEY")
            client = OpenAI(base_url="https://api.deepseek.com", api_key=api_key)
            
            with st.status("🔍 Запуск многослойного аудита...", expanded=True) as status:
                c_text = extract_text(contract_file)
                r_text = extract_text(report_file)
                bad_history = load_bad_history()
                
                if not c_text or not r_text:
                    st.error("❌ Файлы не прочитаны.")
                    st.stop()
                
                status.update(label="🧠 ИИ применяет 3 слоя проверки...", state="running")

                # --- ВОЗВРАЩАЕМ ТОТ САМЫЙ МОЩНЫЙ ПРОМПТ ---
                sys_msg = f"""Ты — максимально придирчивый аудитор госконтрактов. Твоя цель: найти повод НЕ ПРИНИМАТЬ отчет.
                
                ИСПОЛЬЗУЙ 3 СЛОЯ ПРОВЕРКИ:
                1. СЛОЙ ИСТОРИИ (База прошлых отказов):
                {bad_history}
                
                2. ТЕХНИЧЕСКИЙ СЛОЙ (ТЗ):
                Сверь каждый факт, цифру, дату и объем. Малейшее отклонение — нарушение.
                
                3. СЛОЙ ФОРМАЛИЗМА:
                Проверь ИНК, полные названия ведомств, отсутствие стоп-слов ("около", "порядка", "не менее").

                ДЛЯ КАЖДОЙ ОШИБКИ ПИШИ СТРОГО:
                - **Нарушение**: (конкретная суть)
                - **Локация**: (Страница №, Абзац №)
                - **Основание**: (пункт из ТЗ или пункт из Базы отказов)
                - **Риск**: (почему это приведет к штрафу или возврату)"""

                usr_msg = f"""Проведи аудит. Используй маркеры [СТРАНИЦА] и [Абзац] для локации.
                
                КОНТРАКТ (Эталон):
                {c_text[:12000]}
                
                ОТЧЕТ (Объект проверки):
                {r_text[:12000]}"""

                params = {
                    "model": selected_model,
                    "messages": [
                        {"role": "system", "content": sys_msg},
                        {"role": "user", "content": usr_msg}
                    ],
                    "max_tokens": 4000
                }
                
                if selected_model == "deepseek-chat":
                    params["temperature"] = 0.1

                res = client.chat.completions.create(**params)
                
                reasoning = getattr(res.choices[0].message, 'reasoning_content', None)
                report_content = res.choices[0].message.content
                
                status.update(label="✅ Аудит завершен!", state="complete", expanded=False)

            # --- ВЫВОД ---
            if reasoning:
                with st.expander("🔍 Ход мыслей «Вредного Заказчика» (Reasoner)"):
                    st.info(reasoning)

            if report_content:
                st.subheader("📋 Итоговый протокол несоответствий")
                st.markdown(report_content)
                st.download_button("📥 Скачать протокол", data=create_docx(report_content), file_name="Audit.docx")

        except Exception as e:
            st.error(f"❌ Ошибка: {str(e)}")
    else:
        st.warning("⚠️ Загрузите документы.")
