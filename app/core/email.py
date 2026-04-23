import re
import html
from app.services.translations import TranslationService
from app.config.settings import settings

def generate_html_email(subject: str, text_body: str, lang: str = "en") -> str:
    """
    Converts a plain-text email body into a beautiful ASAC 2026 HTML template.
    Automatically extracts URLs to create prominent action buttons.
    """
    # Find the first URL in the text body to use for the main button
    
    translations = TranslationService()
    
    urls = re.findall(r'(https?://[^\s]+)', text_body)
    
    main_url = None
    if urls:
        # Prioritize system action links over URLs pasted in admin comments
        frontend_urls = [url for url in urls if settings.FRONTEND_URL in url]
        main_url = frontend_urls[0] if frontend_urls else urls[0]
    
    # Safely escape HTML to prevent user-generated text (admin comments) from breaking the email layout
    safe_text_body = html.escape(text_body)
    
    # Convert plain text newlines into HTML line breaks
    html_content = safe_text_body.replace('\n', '<br>')
    
    # Automatically turn any URLs in the email body into clickable gold hyperlinks
    html_content = re.sub(r'(https?://[^\s<]+)', r'<a href="\1" style="color: #f0a500; font-weight: 600; word-break: break-all;">\1</a>', html_content)
    
    button_html = ""
    if main_url:
        button_html = f"""
        <div class="url-box">
          <p class="url-display">{main_url}</p>
          <a href="{main_url}" class="url-btn">{translations.get_string('email_access_link_btn', lang)}</a>
        </div>
        <p class="url-hint">{translations.get_string('email_copy_paste_hint', lang)}</p>
        
        <div class="warning-box" role="alert">
          <p class="warning-title">{translations.get_string('email_security_notice_title', lang)}</p>
          <p class="warning-body">
            {translations.get_string('email_security_notice_body', lang)}
          </p>
        </div>
        """

    template = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>___SUBJECT___</title>
  <link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@700;800;900&family=Barlow:wght@400;500;600;700&display=swap" rel="stylesheet"/>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      background-color: #0d1520;
      font-family: 'Barlow', sans-serif;
      padding: 32px 16px;
      -webkit-font-smoothing: antialiased;
    }
    .email-wrapper { max-width: 620px; margin: 0 auto; }
    .email-card { background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 8px 40px rgba(0,0,0,.5); }
    .email-header { background: #0b1622; padding: 24px 48px; display: flex; align-items: center; justify-content: space-between; gap: 14px; border-bottom: 2px solid #f0a500; }
    .logos-wrapper { display: flex; align-items: center; gap: 16px; }
    .header-logo { max-height: 48px; width: auto; object-fit: contain; background-color: #ffffff; padding: 6px 10px; border-radius: 6px; }
    .logo-text-block { display: flex; flex-direction: column; gap: 2px; }
    .logo-wordmark { font-family: 'Barlow Condensed', sans-serif; font-size: 22px; font-weight: 900; color: #ffffff; letter-spacing: 2px; text-transform: uppercase; line-height: 1; }
    .logo-wordmark span { color: #f0a500; }
    .logo-sub { font-size: 10px; font-weight: 600; letter-spacing: 1.5px; text-transform: uppercase; color: #5a7090; }
    .email-body { padding: 40px 48px 48px; background: #ffffff; }
    .headline { font-family: 'Barlow Condensed', sans-serif; font-size: 40px; font-weight: 900; line-height: 1.1; margin-bottom: 8px; letter-spacing: 0.5px; text-transform: uppercase; }
    .headline .dark { color: #0b1622; }
    .headline .gold { color: #f0a500; }
    .subject-line { font-size: 16px; color: #f0a500; font-weight: 700; margin-bottom: 24px; text-transform: uppercase; letter-spacing: 1px;}
    .intro-text { font-size: 15px; color: #455368; line-height: 1.7; margin-bottom: 36px; }
    .url-box { background: #0b1622; border: 2px solid #f0a500; border-radius: 10px; padding: 28px 24px; text-align: center; margin-bottom: 14px; }
    .url-display { font-size: 12px; color: #4a6080; word-break: break-all; margin-bottom: 20px; letter-spacing: 0.2px; line-height: 1.6; }
    .url-btn { display: inline-block; background: #f0a500; color: #0b1622; font-family: 'Barlow Condensed', sans-serif; font-size: 16px; font-weight: 900; letter-spacing: 1.5px; text-transform: uppercase; text-decoration: none; padding: 13px 38px; border-radius: 6px; }
    .url-hint { font-size: 13px; color: #94a3b8; margin-bottom: 32px; line-height: 1.6; text-align: center; }
    .warning-box { background: #fff8e6; border-left: 4px solid #f0a500; border-radius: 0 10px 10px 0; padding: 20px 22px; margin-bottom: 36px; }
    .warning-title { font-family: 'Barlow Condensed', sans-serif; font-size: 17px; font-weight: 800; color: #0b1622; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px; }
    .warning-body { font-size: 13.5px; color: #555; line-height: 1.6; }
    .help-title { font-family: 'Barlow Condensed', sans-serif; font-size: 22px; font-weight: 800; color: #0b1622; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 14px; }
    .help-text { font-size: 14.5px; color: #455368; line-height: 1.65; margin-bottom: 10px; }
    .help-text a { color: #f0a500; font-weight: 600; text-decoration: none; }
    .email-footer { background: #0b1622; padding: 28px 48px; text-align: center; border-top: 2px solid #f0a500; }
    .footer-notice { font-size: 13px; color: #5a7090; line-height: 1.6; margin-bottom: 4px; }
    .footer-support-link { font-size: 13px; color: #f0a500; text-decoration: none; font-weight: 600; }
    @media (max-width: 480px) { .email-header, .email-body, .email-footer { padding-left: 24px; padding-right: 24px; } .headline { font-size: 28px; } }
  </style>
</head>
<body>
<div class="email-wrapper">
  <div class="email-card">
    <!-- Header -->
    <div class="email-header">
      <div class="logos-wrapper">
        <img src="https://ams-fastapi-images-12345.s3.eu-north-1.amazonaws.com/LOGO%20AND%20WORDMARK-02.png" alt="Accra 2026" class="header-logo" />
      </div>
      <div class="logo-text-block" style="text-align: right;">
        <span class="logo-wordmark">ACCRA <span>2026</span></span>
        <span class="logo-sub">Official Accreditation Portal</span>
      </div>
    </div>

    <!-- Body -->
    <div class="email-body">
      <h1 class="headline">
        <span class="dark">ACCRA </span><span class="gold">2026</span>
      </h1>
      <div class="subject-line">___SUBJECT___</div>

      <p class="intro-text">
        ___HTML_CONTENT___
      </p>

      ___BUTTON_HTML___

      <!-- Help -->
      <h2 class="help-title">___HELP_TITLE___</h2>
      <p class="help-text">
        ___IGNORE_TEXT___
      </p>
      <p class="help-text">
        ___CONTACT_INTRO___
        <a href="mailto:accreditation@fasigms.africa">accreditation@fasigms.africa</a>
      </p>
    </div>

    <!-- Footer -->
    <div class="email-footer">
      <p class="footer-notice">
        ___FOOTER_NOTICE___
      </p>
      <a href="mailto:accreditation@fasigms.africa" class="footer-support-link">accreditation@fasigms.africa</a>
    </div>
  </div>
</div>
</body>
</html>
"""
    
    html = template.replace("___HTML_CONTENT___", html_content)
    html = html.replace("___BUTTON_HTML___", button_html)
    html = html.replace("___SUBJECT___", subject)
    
    html = html.replace("___HELP_TITLE___", translations.get_string('email_need_help_title', lang))
    html = html.replace("___IGNORE_TEXT___", translations.get_string('email_ignore_if_not_you', lang))
    html = html.replace("___CONTACT_INTRO___", translations.get_string('email_contact_support_intro', lang))
    html = html.replace("___FOOTER_NOTICE___", translations.get_string('email_footer_notice', lang))
    
    return html