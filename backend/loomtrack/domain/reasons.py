"""Fixed list of delay-reason categories. The AI may only pick from these."""

REASON_CATEGORIES = [
    {"code": "FABRIC_DELAY", "en": "Fabric delay", "ta": "துணி தாமதம்"},
    {"code": "TRIMS_DELAY", "en": "Trims / accessories delay", "ta": "டிரிம்ஸ் தாமதம்"},
    {"code": "MACHINE_BREAKDOWN", "en": "Machine breakdown", "ta": "இயந்திர பழுது"},
    {"code": "LABOUR_SHORTAGE", "en": "Labour shortage / absenteeism", "ta": "ஆள் பற்றாக்குறை"},
    {"code": "POWER_CUT", "en": "Power cut", "ta": "மின்வெட்டு"},
    {"code": "QUALITY_REWORK", "en": "Quality issue / rework", "ta": "தரக் குறைபாடு / மறுவேலை"},
    {"code": "SUBCONTRACTOR_DELAY", "en": "Subcontractor delay (print / wash)", "ta": "வெளி யூனிட் தாமதம்"},
    {"code": "APPROVAL_PENDING", "en": "Buyer approval pending", "ta": "வாங்குபவர் ஒப்புதல் நிலுவை"},
    {"code": "ORDER_CHANGE", "en": "Style / quantity change", "ta": "ஸ்டைல் / அளவு மாற்றம்"},
    {"code": "NO_ISSUE", "en": "No issue reported", "ta": "பிரச்சனை இல்லை"},
    {"code": "OTHER", "en": "Other", "ta": "மற்றவை"},
]

REASON_CODES = [c["code"] for c in REASON_CATEGORIES]
REASON_LABEL_EN = {c["code"]: c["en"] for c in REASON_CATEGORIES}
