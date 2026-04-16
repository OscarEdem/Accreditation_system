# More robust mapping based on Organization Type instead of Name
ORG_TYPE_ALLOWED_CATEGORIES = {
    "Country Team": ["Athlete", "Coaches", "Team Officials", "Medical Staff", "VIP/Guests"],
    "LOC": ["LOC Staff", "Volunteer", "Security", "Transport", "VIP/Guests"],
    "Media": ["Media"],
    "Technical Official": ["Technical Officials"],
    "National Federation": ["Technical Officials", "VIP/Guests"],
    "Volunteer": ["Volunteer"],
    "Service Staff": ["Security", "Transport", "LOC Staff"],
    "VIP/Guest": ["VIP/Guests"],
    "African Federation": ["Technical Officials", "VIP/Guests"],
    "World Federation": ["Technical Officials", "VIP/Guests"],
    "Generic": [] # Default empty list for generic organizations
}

SEEDED_ORGANIZATIONS = [
    "Team Algeria", "Team Angola", "Team Benin", "Team Botswana", "Team Burkina Faso",
    "Team Burundi", "Team Cabo Verde", "Team Cameroon", "Team Central African Republic",
    "Team Chad", "Team Comoros", "Team Congo", "Team Congo (DRC)", "Team Côte d'Ivoire",
    "Team Djibouti", "Team Egypt", "Team Equatorial Guinea", "Team Eritrea", "Team Eswatini",
    "Team Ethiopia", "Team Gabon", "Team Gambia", "Team Ghana", "Team Guinea",
    "Team Guinea-Bissau", "Team Kenya", "Team Lesotho", "Team Liberia", "Team Libya",
    "Team Madagascar", "Team Malawi", "Team Mali", "Team Mauritania", "Team Mauritius",
    "Team Morocco", "Team Mozambique", "Team Namibia", "Team Niger", "Team Nigeria",
    "Team Rwanda", "Team São Tomé and Príncipe", "Team Senegal", "Team Seychelles",
    "Team Sierra Leone", "Team Somalia", "Team South Africa", "Team South Sudan",
    "Team Sudan", "Team Tanzania", "Team Togo", "Team Tunisia", "Team Uganda",
    "Team Zambia", "Team Zimbabwe", "LOC Staff", "Media", "International Technical Official",
    "Ghana Athletics Association", "Volunteer", "Service Staff", "VIP/Guest",
    "Confederation of African Athletics", "World Athletics"
]