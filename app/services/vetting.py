def calculate_dynamic_score(conn, text):
    """
    Calculate testing score dynamically based on rules in the database.
    """
    criteria = conn.execute("SELECT * FROM vetting_criteria").fetchall()
    
    total_score = 0
    words = text.split()
    word_count = len(words)
    
    keyword_list = ['python', 'java', 'management', 'leadership', 'agile', 'development', 'engineer']
    keyword_count = sum(1 for w in words if w.lower() in keyword_list)

    for c in criteria:
        name = c["name"].lower()
        weight = c["weight"]
        
        if "word" in name:
            points = min((word_count / 2), weight)
        elif "keyword" in name or "fluency" in name:
            points = min((keyword_count * 10), weight)
        else:
            points = min(weight * 0.75, weight)
            
        total_score += points

    return min(int(total_score), 100)

def determine_status_and_recommendation(score, threshold):
    if score >= threshold + 20:
        status = "Verified"
        recommendation = "Highly Recommended: This candidate demonstrated exceptional proficiency. Their background and qualifications significantly align with standards of excellence in this sector."
    elif score >= threshold:
        status = "Pending Review"
        recommendation = "Recommended: This candidate possesses solid foundational skills and represents a capable choice for the role."
    else:
        status = "Needs Improvement"
        recommendation = "Needs Review: The candidate may require additional support or verification to meet the standard requirements."
    return status, recommendation
