"""
Versioned showcase scenario definitions accessible to production without importing evaluation.*
"""
from typing import Any, Dict

SCENARIO_VERSION = "1.0.0"

SHOWCASE_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "returning-to-study": {
        "id": "returning-to-study",
        "version": SCENARIO_VERSION,
        "title": "Can I return to study without a degree?",
        "subtitle": "A fictional student has three years of IT support experience and no bachelor's degree.",
        "badge": "Scripted student · Clara responds live",
        "disclaimer": "Demonstration using a fictional university and sample course information. Course suggestions do not confirm admission eligibility.",
        "student_messages": [
            "I'm interested in the Graduate Certificate in Cloud Computing. I have no bachelor's degree, but I worked in IT support for three years. What options do I have?",
            "Please recap what you know about my experience and what remains uncertain.",
        ],
        "criteria": [
            {
                "id": "preserved_facts",
                "title": "Preserved disclosed facts",
                "description": "Retains that the student self-reported no bachelor's degree and three years of IT support experience, without treating self-report as verified admission eligibility.",
            },
            {
                "id": "grounded_advice",
                "title": "Grounded advice",
                "description": "Substantive course requirements and application procedures are supported by retrieved evidence.",
            },
            {
                "id": "honest_uncertainty",
                "title": "Honest uncertainty",
                "description": "Unknown requirements and eligibility remain unknown; unretrieved information is not declared nonexistent.",
            },
        ],
    }
}


# Retain the original protocol for internal transport checks, not a public choice.
from copy import deepcopy
SMOKE_SCENARIO = deepcopy(SHOWCASE_SCENARIOS['returning-to-study'])
SMOKE_SCENARIO['id'] = 'returning-to-study-smoke'
SMOKE_SCENARIO['conversation_timeout_seconds'] = 120
SMOKE_SCENARIO['expected_tool_policy'] = {
    1: {
        'phase': 'Course Discovery & Prerequisite Check',
        'allowed_tools': ['search_courses', 'get_course_detail'],
        'min_calls': 1,
        'max_calls': 2,
        'expected_purpose': 'Retrieve catalog entry and requirements for Graduate Certificate in Cloud Computing.',
        'conversational_reasoning_only': False
    },
    2: {
        'phase': 'Recap & Verification',
        'allowed_tools': ['get_discovery_context'],
        'min_calls': 0,
        'max_calls': 1,
        'expected_purpose': 'Recap known experience and uncertainty, optionally checking messages via get_discovery_context.',
        'conversational_reasoning_only': False
    }
}
SHOWCASE_SCENARIOS['returning-to-study-smoke'] = SMOKE_SCENARIO
SCENARIO_VERSION = '2.0.0'
SHOWCASE_SCENARIOS['returning-to-study'].update({
    'version': SCENARIO_VERSION,
    'title': 'Can I change careers without starting over?',
    'subtitle': 'Meet Alex: returning to study, balancing work, and finding out which experience counts.',
    'conversation_timeout_seconds': 360,
    'student_messages': [
        "I'm Alex. I want to move into cloud computing and I'm interested in the Graduate Certificate in Cloud Computing. I have no bachelor's degree and three years of IT support experience. What options could I explore?",
        "I need to keep working while I study, so I can only consider online courses. Please keep that in mind when looking at my options.",
        "I was assuming an online course would let me study part-time. Does the course information actually confirm that?",
        "I need to correct my experience. Two of those years were coursework. I have one year of professional IT support experience. Does that change whether the Cloud Computing course is a suitable option?",
        "What general application steps are recorded for postgraduate study? Please distinguish those steps from whether I qualify for a particular course.",
        "Please sum up which options, if any, are still worth exploring for me, what changed after my correction, and what remains unknown. If there isn't a confirmed match, please say so."
    ],
    'turn_labels': ['A career goal', 'Fitting study around work', 'Checking an assumption',
                    'Correcting the experience', 'Finding practical next steps', 'Making sense of the options'],
    'expected_tool_policy': {
        1: {
            'phase': 'Course Discovery & Prerequisite Check',
            'allowed_tools': ['search_courses', 'get_course_detail'],
            'min_calls': 1,
            'max_calls': 2,
            'expected_purpose': 'Retrieve catalog entry and requirements for Graduate Certificate in Cloud Computing.',
            'conversational_reasoning_only': False
        },
        2: {
            'phase': 'Delivery Mode Constraint Evaluation',
            'allowed_tools': ['get_discovery_context', 'search_courses'],
            'min_calls': 0,
            'max_calls': 2,
            'expected_purpose': 'Evaluate online study constraint against catalog data; may reuse prior search, search with study_mode_preference="Online", or verify student constraints via get_discovery_context.',
            'conversational_reasoning_only': False
        },
        3: {
            'phase': 'Assumption Verification',
            'allowed_tools': ['get_course_detail', 'search_knowledge', 'get_discovery_context'],
            'min_calls': 0,
            'max_calls': 1,
            'expected_purpose': 'Verify part-time availability or institutional study load policy via course details, knowledge search, or context.',
            'conversational_reasoning_only': False
        },
        4: {
            'phase': 'Fact Correction & Assumption Update',
            'allowed_tools': ['search_courses', 'get_course_detail', 'get_discovery_context'],
            'min_calls': 0,
            'max_calls': 1,
            'expected_purpose': 'Evaluate corrected 1-year experience against course entry requirements via course search, course detail, or context.',
            'conversational_reasoning_only': False
        },
        5: {
            'phase': 'Postgraduate Application Procedure Retrieval',
            'allowed_tools': ['search_knowledge'],
            'min_calls': 1,
            'max_calls': 2,
            'expected_purpose': 'Retrieve institutional guidance on general postgraduate application procedures.',
            'conversational_reasoning_only': False
        },
        6: {
            'phase': 'Synthesis & Next Steps',
            'allowed_tools': ['get_discovery_context'],
            'min_calls': 0,
            'max_calls': 1,
            'expected_purpose': 'Synthesize verified findings and uncertainty; verifies captured messages with get_discovery_context per recap instructions.',
            'conversational_reasoning_only': False
        }
    },
    'criteria': [
        {'id':'preserved_facts','title':"Did Clara understand Alex’s situation?",
         'description':'Remember the online-only constraint and update advice after Alex corrects their experience.'},
        {'id':'grounded_advice','title':'Did the advice match the course information?',
         'description':'Use the recorded requirements and application guidance, without inventing a process.'},
        {'id':'honest_uncertainty','title':"Did Clara explain what she couldn’t confirm?",
         'description':'Separate online delivery from part-time availability and be clear if no suitable match is confirmed.'},
        {'id':'conversation_quality','title':'Did Clara respond clearly and professionally?',
         'description':'Answer the student’s question directly, remain concise, avoid exposing internal instructions or tool-selection reasoning, and use natural spoken language.'}
    ]
})


def get_scenario(scenario_id: str) -> Dict[str, Any] | None:
    return SHOWCASE_SCENARIOS.get(scenario_id)


def get_public_scenario(scenario_id: str) -> Dict[str, Any] | None:
    scenario = get_scenario(scenario_id)
    if not scenario:
        return None
    return {
        "id": scenario["id"],
        "version": scenario["version"],
        "title": scenario["title"],
        "subtitle": scenario["subtitle"],
        "badge": scenario["badge"],
        "disclaimer": scenario["disclaimer"],
        "student_messages": list(scenario["student_messages"]),
        "criteria": list(scenario["criteria"]),
        "turn_labels": list(scenario.get("turn_labels", [])),
        "expected_tool_policy": dict(scenario.get("expected_tool_policy", {})),
    }
