import os
import re
import json
import time
import logging
import urllib.parse
from typing import Dict, Any

import pandas as pd
import streamlit as st
import google.generativeai as genai
from fpdf import FPDF
from dotenv import load_dotenv

# ==========================================
# 1. APPLICATION SETUP 
# ==========================================
st.set_page_config(
    page_title="ZNA Elite Studio | AI Career Architect",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ==========================================
# 2. CORE BACKEND SERVICES
# ==========================================
class AIService:
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
# 3. STATE MANAGEMENT & PREMIUM CSS
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
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
        @import url('https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css');
        
        /* Modern Font */
        html, body, p, div, h1, h2, h3, h4, h5, h6, label { font-family: 'Outfit', sans-serif !important; }
        
        /* Deep Space Background */
        .stApp { background: radial-gradient(circle at 15% 50%, #080d1e, #03050b); color: #f0f6fc; }
        
        /* Glassmorphism Cards */
        .glass-card { 
            background: rgba(15, 23, 42, 0.4); 
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08); 
            border-radius: 20px; 
            padding: 24px; 
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3); 
            margin-bottom: 24px; 
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); 
        }
        .glass-card:hover { 
            transform: translateY(-8px) scale(1.01); 
            border-color: rgba(59, 130, 246, 0.5); 
            box-shadow: 0 15px 45px 0 rgba(59, 130, 246, 0.2);
        }

        /* Neon Inputs */
        .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stSelectbox>div>div>div { 
            background-color: rgba(255, 255, 255, 0.03) !important; 
            color: #f0f6fc !important; 
            border: 1px solid rgba(255, 255, 255, 0.1) !important; 
            border-radius: 12px !important; 
            padding: 12px !important;
        }
        .stTextInput>div>div>input:focus, .stTextArea>div>div>textarea:focus {
            border-color: #00f2fe !important; 
            box-shadow: 0 0 15px rgba(0, 242, 254, 0.3) !important;
        }

        /* Animated Gradient Buttons */
        .stButton>button { 
            border-radius: 50px !important; 
            background: linear-gradient(45deg, #4facfe 0%, #00f2fe 50%, #4facfe 100%) !important; 
            background-size: 200% auto !important;
            color: #000 !important; 
            font-weight: 800 !important; 
            border: none !important; 
            padding: 10px 24px !important;
            box-shadow: 0 4px 15px rgba(0, 242, 254, 0.4) !important; 
            transition: 0.5s !important; 
        }
        .stButton>button:hover { 
            background-position: right center !important; 
            transform: translateY(-3px) !important; 
            box-shadow: 0 8px 25px rgba(0, 242, 254, 0.6) !important; 
        }

        /* Pulse Animation for Status */
        @keyframes pulse-neon { 0% { box-shadow: 0 0 0 0 rgba(0, 242, 254, 0.4); } 70% { box-shadow: 0 0 0 10px rgba(0, 242, 254, 0); } 100% { box-shadow: 0 0 0 0 rgba(0, 242, 254, 0); } }
        .live-pulse { display: inline-block; width: 10px; height: 10px; border-radius: 50%; background-color: #00f2fe; animation: pulse-neon 2s infinite; margin-left: 8px; }
        
        .status-badge { background: rgba(0, 242, 254, 0.1); border: 1px solid rgba(0, 242, 254, 0.3); color: #00f2fe; padding: 8px 16px; border-radius: 50px; font-size: 11px; font-weight: 800; text-transform: uppercase; display: inline-flex; align-items: center; letter-spacing: 1px;}
        
        /* Cool Metrics styling */
        .metric-title { font-size: 12px; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 5px; }
        .metric-value { font-size: 28px; font-weight: 800; background: -webkit-linear-gradient(45deg, #fff, #4facfe); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }

        /* Links */
        .side-job-portal { border-radius: 12px; text-align: center; padding: 12px; font-weight: 600; display: inline-block; width: 100%; margin-top: 10px; text-decoration: none; color: white !important; transition: all 0.3s ease; border: 1px solid rgba(255,255,255,0.1); }
        .side-job-portal:hover { transform: scale(1.05); filter: brightness(1.2); border-color: rgba(255,255,255,0.3); }
        
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 4. FRONTEND VIEWS (THE FUN UI)
# ==========================================

def render_dashboard():
    st.markdown("""<div style='float: right;'><span class='status-badge'>AI Core Online <span class='live-pulse'></span></span></div>""", unsafe_allow_html=True)
    st.title("🚀 Command Center")
    
    status = "Optimized & Ready" if st.session_state['resume_text'] else "Awaiting Data Injection"
    words = len(st.session_state['resume_text'].split())
    job = st.session_state['target_job'] or "Target Not Locked"

    col1, col2, col3 = st.columns(3)
    with col1: 
        st.markdown(f"""
        <div class='glass-card'>
            <div class='metric-title'>Profile Status</div>
            <div class='metric-value' style='font-size:22px;'>{status}</div>
        </div>""", unsafe_allow_html=True)
    with col2: 
        st.markdown(f"""
        <div class='glass-card'>
            <div class='metric-title'>Mission Target</div>
            <div class='metric-value' style='font-size:22px;'>{job}</div>
        </div>""", unsafe_allow_html=True)
    with col3: 
        st.markdown(f"""
        <div class='glass-card'>
            <div class='metric-title'>Neural Memory Loaded</div>
            <div class='metric-value'>{words} <span style='font-size:14px; color:#94a3b8;'>tokens</span></div>
        </div>""", unsafe_allow_html=True)

    d1, d2 = st.columns([0.6, 0.4])
    with d1:
        st.markdown("""<div class='glass-card'><h4><i class='fas fa-crosshairs'></i> Optimization Score</h4>""", unsafe_allow_html=True)
        st.markdown("""
            <div style='padding: 20px; text-align: center;'>
                <div style='font-size: 64px; font-weight: 800; background: -webkit-linear-gradient(45deg, #00f2fe, #4facfe); -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>94%</div>
                <div style='color: #10b981; font-size: 14px; margin-top: 5px; font-weight: 600;'><i class='fas fa-rocket'></i> Top 5% of candidates</div>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    with d2:
        st.markdown("""<div class='glass-card' style='height: 93%;'><h4><i class='fas fa-terminal'></i> Terminal Logs</h4>""", unsafe_allow_html=True)
        st.success("✅ **[SYS_INIT]** Gemini 1.5 Flash Connected.")
        if words > 0: 
            st.info(f"🧠 **[DATA_SYNC]** {words} words vectorized successfully.")
            st.warning("⚡ **[ACTION]** Ready to deploy cover letters & mock interviews.")
        else: 
            st.error("⚠️ **[AWAITING_INPUT]** Go to Resume Builder to begin.")
        st.markdown("</div>", unsafe_allow_html=True)

def render_resume_builder(ai: AIService, pdf: DocumentService):
    st.title("⚡ AI Resume Forge")
    tab1, tab2 = st.tabs(["🛠️ Engineer Context", "✨ Final Masterpiece"])
    
    with tab1:
        st.markdown("""<div class='glass-card'>""", unsafe_allow_html=True)
        style = st.selectbox("Design Architecture:",["Standard Corporate", "Executive & Leadership", "Creative Tech Innovator", "Startup Hustler"])
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Agent Name *", value=st.session_state['user_name'], placeholder="John Doe")
            email = st.text_input("Comms (Email)", value=st.session_state['user_email'])
        with c2:
            target = st.text_input("Target Objective (Role) *", value=st.session_state['target_job'], placeholder="e.g. Senior UX Designer")
            phone = st.text_input("Direct Line (Phone)", value=st.session_state['user_phone'])
            
        raw_data = st.text_area("Raw Experience Data (Paste anything here) *", height=150, placeholder="Dump your old resume, LinkedIn bio, or just bullet points here. The AI will sort it out.")
        
        if st.button("🚀 IGNITE SYNTHESIS"):
            if name and target and raw_data:
                st.session_state.update({'user_name': name, 'target_job': target, 'user_email': email, 'user_phone': phone})
                
                progress_text = "Establishing neural link..."
                my_bar = st.progress(0, text=progress_text)
                for percent_complete in range(100):
                    time.sleep(0.01)
                    if percent_complete == 30: my_bar.progress(percent_complete, text="Parsing raw data blocks...")
                    elif percent_complete == 60: my_bar.progress(percent_complete, text="Injecting ATS keywords...")
                    elif percent_complete == 90: my_bar.progress(percent_complete, text="Polishing final draft...")
                    else: my_bar.progress(percent_complete, text=progress_text)
                
                prompt = f"Act as an expert Resume Writer. Style: {style}. Target Role: {target}. Raw Data: {raw_data}. RULES: Create a PROFESSIONAL SUMMARY. DO NOT write contact info at the top. Organize into UPPERCASE sections. Return ONLY plain text."
                st.session_state['resume_text'] = ai.generate_text(prompt)
                
                my_bar.empty()
                st.toast('Synthesis Complete! Check Tab 2.', icon='🔥')
                st.balloons() 
                
            else: st.error("⚠️ Mission aborted: Missing Required Fields (*)")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        if st.session_state['resume_text']:
            st.session_state['resume_text'] = st.text_area("Fine-tune your document:", value=st.session_state['resume_text'], height=450)
            meta = {'name': st.session_state['user_name'], 'email': st.session_state['user_email'], 'phone': st.session_state['user_phone']}
            pdf_data = pdf.build_resume(st.session_state['resume_text'], meta)
            st.download_button("💾 DOWNLOAD SECURE PDF", data=pdf_data, file_name=f"Resume_{name.replace(' ', '_')}.pdf", mime="application/pdf", type="primary")
        else:
            st.info("👻 Nothing here yet. Ignite synthesis in Tab 1!")

def render_letter_engine(ai: AIService, pdf: DocumentService):
    st.title("✉️ Smart Letter Engine")
    if not st.session_state['resume_text']:
        st.warning("⚠️ The AI needs to know who you are first. Go forge your resume!")
        return

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""<div class='glass-card'>""", unsafe_allow_html=True)
        company = st.text_input("Target Corporation *", placeholder="e.g. SpaceX, Apple")
        hiring_manager = st.text_input("Hiring Lead (Optional)", placeholder="Who are we talking to?")
        job_desc_context = st.text_area("Job Highlights / JD:", height=100, placeholder="Paste the job requirements here...")
        
        if st.button("✨ DRAFT MASTERPIECE"):
            if company:
                with st.spinner("AI is ghostwriting your letter..."):
                    prompt = f"Write cover letter. Target Role: {st.session_state['target_job']}. Company: {company}. Manager: {hiring_manager}. JD Context: {job_desc_context}. Candidate Resume: {st.session_state['resume_text']}. Max 300 words. Plain text."
                    st.session_state['cover_letter_output'] = ai.generate_text(prompt)
                    st.toast("Letter generated!", icon="📝")
            else: st.error("⚠️ We need a target corporation.")
        st.markdown("</div>", unsafe_allow_html=True)
        
    with col2:
        st.markdown("""<div class='glass-card'>""", unsafe_allow_html=True)
        if st.session_state['cover_letter_output']:
            st.text_area("Your Cover Letter:", value=st.session_state['cover_letter_output'], height=250)
            meta = {'name': st.session_state['user_name'], 'email': st.session_state['user_email']}
            pdf_data = pdf.build_resume(st.session_state['cover_letter_output'], meta)
            st.download_button("💾 DOWNLOAD PDF", data=pdf_data, file_name=f"CoverLetter_{company}.pdf", mime="application/pdf", type="primary")
        else:
            st.info("Awaiting command...")
        st.markdown("</div>", unsafe_allow_html=True)

def render_ats_scanner(ai: AIService):
    st.title("🔍 ATS Deep Scan")
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown("""<div class='glass-card'><h4><i class='fas fa-user-shield'></i> Your Active Profile</h4>""", unsafe_allow_html=True)
        if st.session_state['resume_text']:
            st.text_area("", value=st.session_state['resume_text'][:300] + "...\n[Data Securely Loaded]", height=150, disabled=True)
        else: st.error("⚠️ No Profile Loaded.")
        st.markdown("</div>", unsafe_allow_html=True)
            
    with col_r:
        st.markdown("""<div class='glass-card'><h4><i class='fas fa-briefcase'></i> Target Job Description</h4>""", unsafe_allow_html=True)
        job_desc = st.text_area("", height=150, placeholder="Paste the exact job description here...")
        st.markdown("</div>", unsafe_allow_html=True)
    
    if st.button("🔥 RUN DIAGNOSTIC"):
        if st.session_state['resume_text'] and job_desc:
            with st.spinner("Scanning semantic vectors..."):
                prompt = f"Act as an Applicant Tracking System. Resume: {st.session_state['resume_text']}. JD: {job_desc}. Output: 1. Match Score (%) 2. Missing Keywords 3. Recommendation."
                st.info(ai.generate_text(prompt))
                st.toast("Diagnostic Complete", icon="✅")
        else: st.warning("⚠️ Cannot run scan without both Profile and JD.")

def render_interview_prep(ai: AIService):
    st.title("🎙️ AI Interview Simulator")
    if not st.session_state['resume_text']:
        st.warning("⚠️ Forge a resume first so the AI knows what to ask you.")
        return

    st.markdown("""<div class='glass-card'>""", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1: company = st.text_input("Target Company", placeholder="Where are you interviewing?")
    with c2: type_ = st.selectbox("Interrogation Level",["Behavioral (Culture Fit)", "Technical (Hard Skills)", "Executive (Final Boss)"])
    
    if st.button("🎲 GENERATE SCENARIOS"):
        with st.spinner("Generating hyper-specific interview questions..."):
            prompt = f"""
            Act as a Senior Recruiter conducting a {type_} interview for {st.session_state['target_job']} at {company or 'a top firm'}.
            Candidate Resume: {st.session_state['resume_text']}
            Return a JSON object with this exact schema (no markdown):
            {{"questions":[{{"number": 1, "question": "...", "situation": "...", "task": "...", "action": "...", "result": "...", "competencies":["Leadership"]}}]}}
            """
            st.session_state['interview_prep_data'] = ai.generate_json(prompt)
            st.toast("Scenarios Ready!", icon="🎯")
    st.markdown("</div>", unsafe_allow_html=True)

    data = st.session_state.get('interview_prep_data')
    if data and "questions" in data:
        for q in data["questions"]:
            st.markdown(f"""
                <div class='glass-card'>
                    <h3 style='color: #00f2fe;'>Q{q.get('number', 1)}: {q.get('question', '')}</h3>
                    <div style='display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 15px; margin-top: 15px;'>
                        <div style='background: rgba(0,0,0,0.3); padding: 15px; border-radius: 8px; border-left: 3px solid #4facfe;'><b>S:</b> {q.get('situation', '')}</div>
                        <div style='background: rgba(0,0,0,0.3); padding: 15px; border-radius: 8px; border-left: 3px solid #4facfe;'><b>T:</b> {q.get('task', '')}</div>
                        <div style='background: rgba(0,0,0,0.3); padding: 15px; border-radius: 8px; border-left: 3px solid #4facfe;'><b>A:</b> {q.get('action', '')}</div>
                        <div style='background: rgba(0,0,0,0.3); padding: 15px; border-radius: 8px; border-left: 3px solid #4facfe;'><b>R:</b> {q.get('result', '')}</div>
                    </div>
                </div>
            """, unsafe_allow_html=True)

def render_skill_gap_analyzer(ai: AIService):
    st.title("🗺️ Career Roadmap Generator")
    if not st.session_state['resume_text']:
        st.warning("⚠️ Forge your resume first so we know where your starting point is.")
        return

    st.markdown("""<div class='glass-card'>""", unsafe_allow_html=True)
    dream_job = st.text_input("Your Ultimate Dream Job *", placeholder="e.g. Chief Technology Officer")
    if st.button("🗺️ PLOT COURSE"):
        if dream_job:
            with st.spinner(f"Plotting course to {dream_job}..."):
                prompt = f"""
                Act as a Career Coach. Resume: {st.session_state['resume_text']}. Dream Job: {dream_job}.
                Return JSON schema:
                {{"missing_skills":["Skill 1"], "learning_roadmap":[{{"week_number": 1, "goal": "...", "action_items": ["..."], "milestone_project_title": "..."}}]}}
                Return exactly 4 weeks.
                """
                st.session_state['skill_gap_data'] = ai.generate_json(prompt)
                st.toast("Map generated!", icon="🗺️")
        else: st.error("⚠️ Enter a destination to plot a course.")
    st.markdown("</div>", unsafe_allow_html=True)
        
    data = st.session_state.get('skill_gap_data')
    if data and "missing_skills" in data:
        st.markdown("""<div class='glass-card'><h4 style='color:#00f2fe;'><i class='fas fa-exclamation-triangle'></i> Identified Skill Gaps</h4><p style='font-size: 18px;'>""" + " • ".join(data['missing_skills']) + "</p></div>", unsafe_allow_html=True)
        for week in data.get('learning_roadmap', []):
            items = "".join([f"<li style='margin-bottom: 5px;'>{item}</li>" for item in week.get('action_items', [])])
            st.markdown(f"""
                <div class='glass-card'>
                    <h3 style='color: #00f2fe;'>Week {week.get('week_number')}: {week.get('goal')}</h3>
                    <ul style='font-size: 16px;'>{items}</ul>
                    <div style='background: rgba(0,242,254,0.1); padding: 15px; border-radius: 8px; border: 1px solid rgba(0,242,254,0.3); margin-top: 15px;'>
                        <b>🏆 Milestone Project:</b> {week.get('milestone_project_title')}
                    </div>
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
        st.markdown("""
            <div style='display: flex; align-items: center; gap: 15px; margin-bottom: 40px;'>
                <div style='background: linear-gradient(45deg, #4facfe, #00f2fe); width: 45px; height: 45px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-weight: 900; color: black; font-size: 24px; box-shadow: 0 0 15px rgba(0,242,254,0.5);'>Z</div>
                <div style='font-size: 26px; font-weight: 800; color: white;'>Elite Studio</div>
            </div>
        """, unsafe_allow_html=True)
        
        app_mode = st.radio("SYSTEM MODULES",[
            "📊 Command Center", 
            "📄 AI Resume Forge", 
            "✉️ Smart Letter Engine", 
            "🔍 ATS Deep Scan", 
            "🎙️ Interview Simulator", 
            "🗺️ Career Roadmap"
        ])
        
        st.markdown("---")
        if st.session_state['target_job']:
            st.markdown("""
                <div style='color: #94a3b8; font-size: 12px; font-weight: 800; text-transform: uppercase; margin-bottom: 10px;'>
                    🌐 Quick Deploy Portals
                </div>
            """, unsafe_allow_html=True)
            job = urllib.parse.quote(st.session_state['target_job'])
            st.markdown(f"""
                <a href='https://www.linkedin.com/jobs/search/?keywords={job}' target='_blank' class='side-job-portal' style='background: rgba(10, 102, 194, 0.2); border-color: #0a66c2;'>
                    <i class='fab fa-linkedin' style='color: #0a66c2;'></i> LinkedIn Search ↗
                </a>
                <a href='https://in.indeed.com/jobs?q={job}' target='_blank' class='side-job-portal' style='background: rgba(37, 87, 167, 0.2); border-color: #2557a7;'>
                    <i class='fas fa-info-circle' style='color: #2557a7;'></i> Indeed Search ↗
                </a>
            """, unsafe_allow_html=True)

    # ---------------- Page Rendering Logic ----------------
    if app_mode == "📊 Command Center":
        render_dashboard()
    elif app_mode == "📄 AI Resume Forge":
        render_resume_builder(ai_service, pdf_service)
    elif app_mode == "✉️ Smart Letter Engine":
        render_letter_engine(ai_service, pdf_service)
    elif app_mode == "🔍 ATS Deep Scan":
        render_ats_scanner(ai_service)
    elif app_mode == "🎙️ Interview Simulator":
        render_interview_prep(ai_service)
    elif app_mode == "🗺️ Career Roadmap":
        render_skill_gap_analyzer(ai_service)

if __name__ == "__main__":
    main()
