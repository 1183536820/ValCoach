"""Shared CSS styles for ValCoach app pages and reports."""

APP_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

* { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }

.main-header { text-align: center; padding: 2.5rem 1rem 1.5rem; }
.main-header h1 { font-size: 3.2rem; background: linear-gradient(135deg, #ff4655, #ff6b81, #ff8a9e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 0.5rem; letter-spacing: -0.5px; }
.main-header p { font-size: 1.15rem; color: #999; font-weight: 400; }

.stButton > button {
    background: linear-gradient(135deg, #ff4655, #e63946);
    color: white; border: none; font-size: 1.05rem;
    padding: 0.6rem 2rem; width: 100%;
    border-radius: 8px;
    transition: all 0.3s ease;
    box-shadow: 0 4px 15px rgba(255,70,85,0.3);
}
.stButton > button:hover {
    background: linear-gradient(135deg, #e63946, #c5303c);
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(255,70,85,0.4);
}

.glass-card {
    background: rgba(255,255,255,0.04);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-radius: 16px;
    padding: 24px;
    margin: 12px 0;
    border: 1px solid rgba(255,255,255,0.08);
    transition: all 0.3s ease;
}
.glass-card:hover {
    border-color: rgba(255,70,85,0.3);
    box-shadow: 0 8px 32px rgba(255,70,85,0.08);
}
.glass-card h3 { color: #ff4655; margin-bottom: 8px; font-weight: 600; }
.glass-card p { color: #aaa; font-size: 14px; line-height: 1.6; }

.footer {
    text-align: center;
    color: #555;
    font-size: 0.8rem;
    padding: 2rem 0;
    border-top: 1px solid rgba(255,255,255,0.05);
    margin-top: 2rem;
}

.step-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 20px 16px;
    text-align: center;
    transition: all 0.3s ease;
    height: 100%;
}
.step-card:hover {
    border-color: rgba(255,70,85,0.25);
    transform: translateY(-2px);
    box-shadow: 0 6px 24px rgba(255,70,85,0.06);
}
.step-card h4 { color: #ff4655; font-size: 1.6rem; margin: 0 0 8px; }
.step-card p { color: #ccc; font-size: 0.9rem; margin: 4px 0; }
.step-card .step-label { font-weight: 600; color: #e0e0e0; font-size: 0.95rem; }

.premium-lock {
    background: linear-gradient(135deg, rgba(255,70,85,0.08), rgba(255,70,85,0.03));
    border-radius: 16px;
    padding: 32px;
    text-align: center;
    margin: 20px 0;
    border: 1px solid rgba(255,70,85,0.2);
}
.premium-lock h3 { color: #ff4655; font-size: 1.4rem; }
.feature-list { list-style: none; padding: 0; margin: 16px 0; }
.feature-list li { padding: 10px 0; color: #ccc; font-size: 14px; border-bottom: 1px solid rgba(255,255,255,0.04); }
.feature-list li:last-child { border-bottom: none; }

.source-badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    margin-left: 8px;
}
.source-badge.local { background: rgba(76,175,80,0.15); color: #66bb6a; }
.source-badge.riot { background: rgba(255,70,85,0.15); color: #ff4655; }
.source-badge.demo { background: rgba(255,193,7,0.15); color: #ffd54f; }

div[data-testid="stRadio"] > label { font-weight: 600; font-size: 0.9rem; color: #aaa; margin-bottom: 8px; }
div[data-testid="stRadio"] > div { gap: 4px; }
div[data-testid="stRadio"] > div label {
    padding: 8px 14px;
    border-radius: 8px;
    transition: all 0.2s ease;
    background: transparent;
}
div[data-testid="stRadio"] > div label:hover { background: rgba(255,255,255,0.04); }

div[data-testid="stTextInput"] label { font-weight: 500; color: #ccc; }
div[data-testid="stTextInput"] input {
    border-radius: 8px;
    border: 1px solid rgba(255,255,255,0.1);
    background: rgba(0,0,0,0.3);
    padding: 10px 14px;
    color: #e0e0e0;
    transition: border-color 0.2s ease;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #ff4655;
    box-shadow: 0 0 0 2px rgba(255,70,85,0.15);
}

.status-msg {
    padding: 12px 16px;
    border-radius: 8px;
    margin: 8px 0;
    font-size: 14px;
}

.report-container {
    border-radius: 16px;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,0.08);
    margin: 20px 0;
}
"""

REPORT_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    color: #e0e0e0;
    min-height: 100vh;
    padding: 20px;
}
.container { max-width: 900px; margin: 0 auto; background: rgba(255, 255, 255, 0.05); border-radius: 16px; padding: 40px; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
.header { text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
.header h1 { font-size: 28px; background: linear-gradient(90deg, #ff4655, #ff6b81); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }
.header .subtitle { color: #888; font-size: 14px; }
.header .player-id { font-size: 20px; color: #e0e0e0; margin-top: 12px; }
.section-title { font-size: 20px; margin: 30px 0 20px; color: #e0e0e0; padding-left: 12px; border-left: 3px solid #ff4655; }
.chart-container { display: flex; justify-content: center; margin: 20px 0; background: rgba(0, 0, 0, 0.2); border-radius: 12px; padding: 20px; }
table { width: 100%; border-collapse: collapse; margin: 20px 0; background: rgba(0, 0, 0, 0.2); border-radius: 12px; overflow: hidden; }
th { background: rgba(255, 70, 85, 0.15); padding: 12px 16px; text-align: left; font-weight: 600; font-size: 14px; color: #ccc; }
td { padding: 12px 16px; border-top: 1px solid rgba(255, 255, 255, 0.05); font-size: 14px; }
tr:hover { background: rgba(255, 255, 255, 0.03); }
.diagnosis-card, .strength-card { background: rgba(0, 0, 0, 0.2); border-radius: 10px; padding: 20px; margin: 16px 0; }
.diagnosis-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.metric-name { font-size: 18px; font-weight: 600; color: #e0e0e0; }
.gap-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 14px; font-weight: 600; }
.diagnosis-detail { font-size: 13px; color: #888; margin-bottom: 10px; }
.diagnosis-advice { font-size: 14px; line-height: 1.6; color: #ccc; }
.footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid rgba(255, 255, 255, 0.1); text-align: center; font-size: 12px; color: #666; line-height: 1.8; }
@media (max-width: 600px) {
    body { padding: 10px; }
    .container { padding: 16px; }
    .header h1 { font-size: 22px; }
    table { font-size: 12px; }
    th, td { padding: 8px 10px; }
    .metric-name { font-size: 15px; }
}
"""

VIDEO_REPORT_CSS = """
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    color: #e0e0e0;
    min-height: 100vh;
    padding: 20px;
}
.container { max-width: 1000px; margin: 0 auto; }
.card { background: rgba(255, 255, 255, 0.05); border-radius: 16px; padding: 30px; margin-bottom: 24px; backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }
.header { text-align: center; padding: 40px 30px; }
.header h1 { font-size: 28px; background: linear-gradient(90deg, #ff4655, #ff6b81); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 8px; }
.header .subtitle { color: #888; font-size: 14px; }
.section-title { font-size: 20px; margin-bottom: 20px; color: #e0e0e0; padding-left: 12px; border-left: 3px solid #ff4655; }
.chart-container { display: flex; justify-content: center; margin: 16px 0; background: rgba(0, 0, 0, 0.2); border-radius: 12px; padding: 16px; }
table { width: 100%; border-collapse: collapse; margin: 16px 0; background: rgba(0, 0, 0, 0.2); border-radius: 12px; overflow: hidden; }
th { background: rgba(255, 70, 85, 0.15); padding: 10px 14px; text-align: left; font-weight: 600; font-size: 14px; color: #ccc; }
td { padding: 10px 14px; border-top: 1px solid rgba(255, 255, 255, 0.05); font-size: 14px; }
tr:hover { background: rgba(255, 255, 255, 0.03); }
.metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 20px 0; }
.metric-card { background: rgba(0, 0, 0, 0.2); border-radius: 12px; padding: 20px; text-align: center; }
.metric-value { font-size: 32px; font-weight: 700; color: #ff4655; }
.metric-label { font-size: 13px; color: #888; margin-top: 4px; }
.diagnosis-card { background: rgba(0, 0, 0, 0.2); border-radius: 10px; padding: 20px; margin: 16px 0; }
.diagnosis-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.metric-name { font-size: 16px; font-weight: 600; color: #e0e0e0; }
.severity-badge { display: inline-block; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.diagnosis-detail { font-size: 13px; color: #888; margin-bottom: 8px; }
.diagnosis-advice { font-size: 14px; line-height: 1.6; color: #ccc; }
.footer { margin-top: 40px; padding-top: 20px; border-top: 1px solid rgba(255, 255, 255, 0.1); text-align: center; font-size: 12px; color: #666; }
@media (max-width: 600px) { body { padding: 10px; } .card { padding: 16px; } .header h1 { font-size: 22px; } .metric-value { font-size: 26px; } }
"""
