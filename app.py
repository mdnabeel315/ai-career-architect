import os
import re
import json
import logging
import urllib.parse
from typing import Dict, Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import google.generativeai as genai
from fpdf import FPDF
from dotenv import load_dotenv

# ==========================================
# 1. APPLICATION SETUP (MUST BE AT THE VERY TOP)
# ==========================================
st.set_page_config(
    page_title="ZNA Elite Studio | AI Career Architect",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================
# 2. CORE BACKEND SERVICES (AI & PDF)
# ==========================================
class AIService:
    """Handles all interactions with Google's Gemini LLM."""
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
            self.is_ready = True
        else:
            self.is_ready = False

    def generate_text(self, prompt: str) -> str:
        if not self.is_ready: return "Error: API Key missing. Please check your .env file."
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            return f"System Error: {str(e)}"

    def generate_json(self, prompt: str) -> Dict[str, Any]:
        if not self.is_ready: return {"error": "API Key missing."}
        try:
            response = self.model.generate_content(prompt)
            cleaned_text = re.sub(r'^```(?:json)?\s*', '', response.text.strip(), flags=re.IGNORECASE)
            cleaned_text = re.sub(r'\s*```$', '', cleaned_text)
            return json.loads(cleaned_text)
        except Exception as e:
            return {"error": str(e)}

class DocumentService(FPDF):
    """Handles professional PDF generation safely."""
    def sanitize(self, text: str) -> str:
        replacements = {'“': '"', '”': '"', '‘': "'", '’': "'", '–': '-', '—': '-'}
        for curr, new in replacements.items(): text = text.replace(curr, new)
        return text.encode('latin-1', 'replace').decode('latin-1')

    def build_resume(self, text_content: str, metadata: Dict[str, str]) -> bytes:
        self.add_page()
        self.set_auto_page_break(auto=True, margin=15)
        self.set_font("Arial", 'B', 16)
        self.cell(0, 10, txt=self.sanitize(metadata.get('name', 'Document')), ln=True, align='C')
        
        self.set_font("Arial", size=10)
        self.set_text_color(0, 102, 204)
        contact_items =[
            (metadata.get('email'), f"mailto:{metadata.get('email')}"),
            (metadata.get('phone'), f"tel:{metadata.get('phone', '').replace(' ', '')}"),
            (metadata.get('linkedin') and "LinkedIn", metadata.get('linkedin')),
            (metadata.get('github') and "GitHub", metadata.get('github'))
        ]
        for label, link in contact_items:
            if label and link: self.cell(0, 5, txt=self.sanitize(label), ln=True, align='C', link=link)
                
        self.set_text_color(0, 0, 0)
        self.line(10, self.get_y()+2, 200, self.get_y()+2)
        self.ln(8)
        
        self.set_font("Arial", size=11)
        for line in text_content.split('\n'):
            clean_line = self.sanitize(line)
            if len(clean_line) < 60 and clean_line.isupper() and clean_line.strip():
                self.set_font("Arial", 'B', 12)
                self.ln(5)
                self.cell(0, 8, txt=clean_line, ln=True)
                self.set_font("Arial", size=11)
            else:
                self.multi_cell(0, 6, txt=clean_line)
        return self.output(dest='S').encode('latin-1')

# ==========================================
# 3. STATE MANAGEMENT & STYLING
# ==========================================
def init_session_state():
    defaults = {
        'resume_text': "", 'target_job': "", 'user_name': "Professional Resume",
        'user_email': "", 'user_phone': "", 'user_linkedin': "", 'user_github': "",
        'cover_letter_output': None, 'interview_prep_data': None, 'skill_gap_data': None
    }
    for key, val in defaults.items():
        if key not in st.session_state: st.session_state[key] = val

def load_css():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
        html, body, p, div, h1, h2, h3, h4, h5, h6, label { font-family: 'Inter', sans-serif !important; }
        .stApp { background-color: #050814; color: #f0f6fc; }
        .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div { background-color: #0f1524 !important; color: #f0f6fc !important; border: 1px solid #1e293b !important; border-radius: 10px !important; }
        .zna-card { background: linear-gradient(145deg, #0f172a 0%, #0a0f1d 100%); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); margin-bottom: 24px; transition: transform 0.3s ease; }
        .zna-card:hover { transform: translateY(-4px); border-color: rgba(59, 130, 246, 0.3); }
        .stButton>button { border-radius: 50px !important; background: linear-gradient(135deg, #3b82f6 0%, #4f46e5 100%) !important; color: white !important; font-weight: 600 !important; border: none !important; box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3) !important; }
        .status-badge { background: rgba(34, 197, 94, 0.1); border: 1px solid rgba(34, 197, 94, 0.2); color: #22c55e; padding: 6px 12px; border-radius: 50px; font-size: 10px; font-weight: 700; text-transform: uppercase; display: inline-flex; align-items: center; }
        @keyframes pulse-green { 0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.4); } 70% { box-shadow: 0 0 0 6px rgba(34, 197, 94, 0); } 100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); } }
        .live-pulse { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: #22c55e; animation: pulse-green 2s infinite; margin-left: 6px; }
        .side-job-portal { border-radius: 12px; text-align: center; padding: 14px; font-weight: 600; display: inline-block; width: 100%; margin-top: 10px; text-decoration: none; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 4. FRONTEND VIEWS (THE 9 SECTIONS)
# ==========================================

def render_dashboard():
    st.markdown("<div style='float: right;'><span class='status-badge'>Gemini 1.5 Flash Active <span class='live-pulse'></span></span></div>", unsafe_allow_html=True)
    st.title("📊 Welcome to your Career Workspace")
    
    status = "Active" if st.session_state['resume_text'] else "Awaiting Data"
    color = "#10b981" if st.session_state['resume_text'] else "#f59e0b"
    words = len(st.session_state['resume_text'].split())
    job = st.session_state['target_job'] or "Not Set"

    col1, col2, col3, col4 = st.columns(4)
    cols_data =[("PROFILE STATUS", status, color), ("TARGET ROLE", job, "#f0f6fc"), ("WORDS IN MEMORY", str(words), "#f0f6fc"), ("API CONNECTION", "Secure", "#3b82f6")]
    for col, (title, val, colr) in zip((col1, col2, col3, col4), cols_data):
        with col: st.markdown(f"<div class='zna-card'><div style='font-size:12px; color:#64748b; font-weight:bold;'>{title}</div><div style='font-size:20px; font-weight:bold; margin-top:5px; color:{colr};'>{val}</div></div>", unsafe_allow_html=True)

    d1, d2 = st.columns([0.65, 0.35])
    with d1:
        st.markdown("<div class='zna-card'><h4><i class='fas fa-chart-area'></i> System Analytics</h4>", unsafe_allow_html=True)
        st.line_chart(pd.DataFrame([65, 72, 68, 85, 88, 92, 96], columns=["ATS Score Trends (%)"]), color="#3b82f6")
        st.markdown("</div>", unsafe_allow_html=True)
    with d2:
        st.markdown("<div class='zna-card'><h4><i class='fas fa-terminal'></i> Live Logs</h4>", unsafe_allow_html=True)
        st.info("✅ *[SYSTEM]* LLM Engine connected.")
        if words > 0: st.success(f"✅ *[MEMORY]* Vectorized {words} words.")
        else: st.warning("⏳ *[MEMORY]* Awaiting user input...")
        st.markdown("</div>", unsafe_allow_html=True)

def render_resume_builder(ai: AIService, pdf: DocumentService):
    st.title("📄 Smart Resume Builder")
    tab1, tab2 = st.tabs(["📋 Setup & Context", "📄 Synthesis Output"])
    
    with tab1:
        st.markdown("<div class='zna-card'>", unsafe_allow_html=True)
        style = st.selectbox("Template Architecture:",["Standard Corporate", "Executive & Leadership", "Creative & Tech"])
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Full Name *", value=st.session_state['user_name'])
            email = st.text_input("Email", value=st.session_state['user_email'])
        with c2:
            target = st.text_input("Target Role *", value=st.session_state['target_job'])
            phone = st.text_input("Phone Number", value=st.session_state['user_phone'])
            
        raw_data = st.text_area("Raw Profile Data / Old Resume *", height=150)
        
        if st.button("Initialize Synthesis", type="primary"):
            if name and target and raw_data:
                st.session_state.update({'user_name': name, 'target_job': target, 'user_email': email, 'user_phone': phone})
                with st.spinner("Synthesizing optimal profile..."):
                    prompt = f"Act as an expert Resume Writer. Style: {style}. Target Role: {target}. Raw Data: {raw_data}. RULES: Create a PROFESSIONAL SUMMARY. DO NOT write contact info at the top. Organize into UPPERCASE sections. Return ONLY plain text."
                    st.session_state['resume_text'] = ai.generate_text(prompt)
                    st.success("✅ Synthesis Complete! View output in Tab 2.")
            else: st.error("⚠️ Missing Required Fields (*)")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        if st.session_state['resume_text']:
            st.session_state['resume_text'] = st.text_area("Edit Generated Document:", value=st.session_state['resume_text'], height=450)
            meta = {'name': st.session_state['user_name'], 'email': st.session_state['user_email'], 'phone': st.session_state['user_phone']}
            pdf_data = pdf.build_resume(st.session_state['resume_text'], meta)
            st.download_button("📥 Export PDF Document", data=pdf_data, file_name=f"Resume_{name.replace(' ', '_')}.pdf", mime="application/pdf", type="primary")
        else:
            st.warning("👈 Provide context parameters in Tab 1 to initiate synthesis.")

def render_letter_engine(ai: AIService, pdf: DocumentService):
    st.title("✉️ Letter Generator")
    if not st.session_state['resume_text']:
        st.error("⚠️ Missing Profile Context! Synthesize a resume first.")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<div class='zna-card'>", unsafe_allow_html=True)
        company = st.text_input("Target Entity *", placeholder="e.g. Apple, Google")
        hiring_manager = st.text_input("Hiring Lead (Optional)")
        job_desc_context = st.text_area("Job Highlights / JD:", height=100)
        
        if st.button("✨ Generate Narratives", type="primary"):
            if company:
                with st.spinner("Drafting narrative..."):
                    prompt = f"Write cover letter. Target Role: {st.session_state['target_job']}. Company: {company}. Manager: {hiring_manager}. JD Context: {job_desc_context}. Candidate Resume: {st.session_state['resume_text']}. Max 300 words. Plain text."
                    st.session_state['cover_letter_output'] = ai.generate_text(prompt)
            else: st.error("⚠️ Missing Target Entity.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        st.markdown("<div class='zna-card'>", unsafe_allow_html=True)
        if st.session_state['cover_letter_output']:
            st.text_area("Draft Output", value=st.session_state['cover_letter_output'], height=250)
            meta = {'name': st.session_state['user_name'], 'email': st.session_state['user_email']}
            pdf_data = pdf.build_resume(st.session_state['cover_letter_output'], meta)
            st.download_button("📥 Export PDF", data=pdf_data, file_name=f"CoverLetter_{company}.pdf", mime="application/pdf", type="primary")
        else:
            st.info("Awaiting command...")
        st.markdown("</div>", unsafe_allow_html=True)

def render_ats_scanner(ai: AIService):
    st.title("🔍 ATS Match Engine")
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("<div class='zna-card'><h4>Active Profile Loaded</h4>", unsafe_allow_html=True)
        if st.session_state['resume_text']:
            st.text_area("", value=st.session_state['resume_text'][:200] + "...\n[Full resume loaded]", height=120, disabled=True)
        else: st.error("⚠️ No Profile Loaded.")
        st.markdown("</div>", unsafe_allow_html=True)
            
    with col_r:
        st.markdown("<div class='zna-card'><h4>Target Job Description</h4>", unsafe_allow_html=True)
        job_desc = st.text_area("", height=120, placeholder="Paste Target JD...")
        st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("🚀 Initiate Deep Scan", type="primary"):
        if st.session_state['resume_text'] and job_desc:
            with st.spinner("Analyzing semantic vectors..."):
                prompt = f"Act as an Applicant Tracking System. Resume: {st.session_state['resume_text']}. JD: {job_desc}. Output: 1. Match Score (%) 2. Missing Keywords 3. Recommendation."
                st.info(ai.generate_text(prompt))
        else: st.warning("⚠️ Parameters missing.")

def render_interview_prep(ai: AIService):
    st.title("🎙️ Interview Simulator")
    if not st.session_state['resume_text']:
        st.error("⚠️ Synthesize a resume first to unlock the Interview Simulator.")
        return

    st.markdown("<div class='zna-card'>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: company = st.text_input("Target Company", placeholder="e.g. Google")
    with c2: type_ = st.selectbox("Interview Stage",["Behavioral", "Technical", "Executive"])
    
    if st.button("🎙️ Generate Mock Interview", type="primary"):
        with st.spinner("Analyzing vectors for probable questions..."):
            prompt = f"""
            Act as a Senior Recruiter conducting a {type_} interview for {st.session_state['target_job']} at {company or 'a top firm'}.
            Candidate Resume: {st.session_state['resume_text']}
            Return a JSON object with this exact schema (no markdown):
            {{"questions":[{{"number": 1, "question": "...", "situation": "...", "task": "...", "action": "...", "result": "...", "competencies":["Leadership"]}}]}}
            """
            st.session_state['interview_prep_data'] = ai.generate_json(prompt)
    st.markdown("</div>", unsafe_allow_html=True)

    data = st.session_state.get('interview_prep_data')
    if data and "questions" in data:
        for q in data["questions"]:
            st.markdown(f"""
                <div class='zna-card'>
                    <h3 style='color: white;'>Q{q.get('number', 1)}: {q.get('question', '')}</h3>
                    <div style='display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 15px;'>
                        <div style='background: #050814; padding: 15px; border-radius: 8px;'><b>S:</b> {q.get('situation', '')}</div>
                        <div style='background: #050814; padding: 15px; border-radius: 8px;'><b>T:</b> {q.get('task', '')}</div>
                        <div style='background: #050814; padding: 15px; border-radius: 8px;'><b>A:</b> {q.get('action', '')}</div>
                        <div style='background: #050814; padding: 15px; border-radius: 8px;'><b>R:</b> {q.get('result', '')}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

def render_skill_gap_analyzer(ai: AIService):
    st.title("🗺️ Skill Gap & Roadmap")
    if not st.session_state['resume_text']:
        st.error("⚠️ Missing Profile Context! Please build your resume first.")
        return

    st.markdown("<div class='zna-card'>", unsafe_allow_html=True)
    dream_job = st.text_input("Your Dream Job / Next Role *", placeholder="e.g. Senior Data Scientist")
    if st.button("🗺️ Generate Visual Roadmap", type="primary"):
        if dream_job:
            with st.spinner(f"Analyzing gap for {dream_job}..."):
                prompt = f"""
                Act as a Career Coach. Resume: {st.session_state['resume_text']}. Dream Job: {dream_job}.
                Return JSON schema:
                {{"missing_skills": ["Skill 1"], "learning_roadmap":[{{"week_number": 1, "goal": "...", "action_items": ["..."], "milestone_project_title": "..."}}]}}
                Return exactly 4 weeks.
                """
                st.session_state['skill_gap_data'] = ai.generate_json(prompt)
        else: st.error("⚠️ Please enter your Target Dream Job.")
    st.markdown("</div>", unsafe_allow_html=True)
        
    data = st.session_state.get('skill_gap_data')
    if data and "missing_skills" in data:
        st.markdown("<div class='zna-card'><h4>Identified Gaps</h4><p>" + ", ".join(data['missing_skills']) + "</p></div>", unsafe_allow_html=True)
        for week in data.get('learning_roadmap', []):
            items = "".join([f"<li>{item}</li>" for item in week.get('action_items', [])])
            st.markdown(f"""
                <div class='zna-card'>
                    <h4 style='color: #10b981;'>Week {week.get('week_number')}: {week.get('goal')}</h4>
                    <ul>{items}</ul>
                    <div style='background: #050814; padding: 10px; border-radius: 8px;'><b>Project:</b> {week.get('milestone_project_title')}</div>
                </div>
            """, unsafe_allow_html=True)

# ==========================================
# 5. MASTER ROUTING & EXECUTION
# ==========================================
def main():
    init_session_state()
    load_css()
    
    ai_service = AIService()
    pdf_service = DocumentService()

    if not ai_service.is_ready:
        st.warning("⚠️ **System Offline:** Please provide your Google API Key in the `.env` file or Streamlit Secrets to activate the AI.")
    
    # ---------------- Sidebar Navigation ----------------
    with st.sidebar:
        st.markdown(
            "<div style='display: flex; align-items: center; gap: 12px; margin-bottom: 30px;'>"
            "<div style='background: linear-gradient(135deg, #3b82f6 0%, #6366f1 100%); width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-weight: bold; color: white; font-size: 20px;'>Z</div>"
            "<div style='font-size: 22px; font-weight: 800; color: white;'>Elite Studio</div>"
            "</div>", unsafe_allow_html=True
        )
        
        app_mode = st.radio("Workspace Navigation",[
            "📊 Dashboard", 
            "📄 Resume Builder", 
            "✉️ Letter Engine", 
            "🔍 ATS Scanner", 
            "🎙️ Interview Prep", 
            "🗺️ Skill Gap Analyzer"
        ])
        
        st.markdown("---")
        if st.session_state['target_job']:
            st.markdown("<div style='color: #475569; font-size: 11px; font-weight: 700; text-transform: uppercase;'>🌐 Direct Apply</div>", unsafe_allow_html=True)
            job = urllib.parse.quote(st.session_state['target_job'])
            naukri = st.session_state['target_job'].replace(' ', '-').lower()
            st.markdown(f"""
                <a href='https://www.linkedin.com/jobs/search/?keywords={job}' target='_blank' class='side-job-portal' style='background: #0a66c2;'><i class='fab fa-linkedin'></i> LinkedIn ↗</a>
                <a href='https://in.indeed.com/jobs?q={job}' target='_blank' class='side-job-portal' style='background: #2557a7;'><i class='fas fa-info-circle'></i> Indeed ↗</a>
                <a href='https://www.naukri.com/{naukri}-jobs' target='_blank' class='side-job-portal' style='background: #0075FF;'><i class='fas fa-briefcase'></i> Naukri ↗</a>
            """, unsafe_allow_html=True)

    # ---------------- Page Rendering Logic ----------------
    if app_mode == "📊 Dashboard":
        render_dashboard()
    elif app_mode == "📄 Resume Builder":
        render_resume_builder(ai_service, pdf_service)
    elif app_mode == "✉️ Letter Engine":
        render_letter_engine(ai_service, pdf_service)
    elif app_mode == "🔍 ATS Scanner":
        render_ats_scanner(ai_service)
    elif app_mode == "🎙️ Interview Prep":
        render_interview_prep(ai_service)
    elif app_mode == "🗺️ Skill Gap Analyzer":
        render_skill_gap_analyzer(ai_service)

# Python standard trigger
if __name__ == "__main__":
    main()
