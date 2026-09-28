import sys
from pathlib import Path

import streamlit as st



# Project imports
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agents import AcademicAgent



# Streamlit configuration

st.set_page_config(
    page_title="Postman: BITS Academic Course Recommender",
    layout="wide",
)



# Academic agent

@st.cache_resource
def get_agent():
    return AcademicAgent()


a = get_agent()
r = a.r



# Page header


st.title("Postman: BITS Academic Course Recommender")
st.caption("Get to know which courses satisfy your wants and your academic requirements")



# Student profile

with st.sidebar:
    st.header("Student profile")

    campus = st.selectbox(
        "Campus",
        ["Pilani", "Goa", "Hyderabad"],
    )

    year = st.number_input(
        "Admission year",
        min_value=2020,
        max_value=2026,
        value=2025,
    )

    program = st.selectbox(
        "Programme",
        ["B.E. Computer Science"],
    )

    sem = st.selectbox(
        "Current semester",
        list(range(1, 9)),
        index=2,
    )

    completed = st.text_area(
        "Completed course codes",
        placeholder="CS F111\nMATH F101\nCHEM F101",
    )

    current = st.text_area(
        "Current course codes",
        placeholder="CS F213\nCS F214",
    )

    interests = st.text_input(
        "Interests",
        placeholder="AI, data science, systems",
    )



# Student profile object


profile = {
    "campus": campus,
    "admission_year": year,
    "program": program,
    "current_semester": sem,
    "completed": [
        x.strip().upper()
        for x in completed.splitlines()
        if x.strip()
    ],
    "current": [
        x.strip().upper()
        for x in current.splitlines()
        if x.strip()
    ],
    "interests": interests,
}


# Academic requirement analysis

academic_state = r.academic_state(profile)

metrics = st.columns(4)

metrics[0].metric(
    "Remaining CDCs",
    len(academic_state["remaining_core"]),
)

metrics[1].metric(
    "Remaining HUEL courses",
    academic_state["huel_courses_remaining"],
)

metrics[2].metric(
    "Remaining HUEL units",
    academic_state["huel_units_remaining"],
)

metrics[3].metric(
    "DE units remaining",
    academic_state["de_units_remaining"],
)


with st.expander("Academic requirement analysis", expanded=True):
    st.write(
        "**Remaining foundation/prescribed:**",
        ", ".join(academic_state["remaining_foundation"])
        or "None",
    )

    st.write(
        "**Remaining CSE core:**",
        ", ".join(academic_state["remaining_core"])
        or "None",
    )

    st.info(
        "Eligibility is evaluated before preference matching."
    )



# Course recommendation


st.subheader("Ask the recommender")

query = st.text_input(
    "What are you looking for?",
    placeholder="Suggest DELs related to AI with no attendance policy",
)


if st.button(
    "Recommend",
    type="primary",
    disabled=not query.strip(),
):

    results, updated_state, trace, schedule_found = a.run(
        profile,
        query,
    )

  
    # Recommended courses
  

    if not results:
        st.warning(
            "No courses matched the supplied requirements and preferences."
        )

    for index, result in enumerate(results, start=1):

        course = result["course"]

        with st.container(border=True):

            st.markdown(
                f'### {index}. '
                f'{course["course_code"]} — '
                f'{course["title"].title()}'
            )

            
            # Human-readable eligibility
            

            eligibility_labels = {
                "eligible": "✓ Eligible",
                "not_eligible": "✗ Not eligible",
                "verification_required": "⚠ Needs verification",
            }

            eligibility = eligibility_labels.get(
                result["eligibility"],
                result["eligibility"],
            )

            st.write(
                f'**Category:** {course["category"]} · '
                f'**Units:** {course["units"]} · '
                f'**Eligibility:** {eligibility} · '
                f'**Match:** {result["score"]}'
            )

            
            # Description
            

            if course.get("description"):
                description = course["description"]

                if len(description) > 700:
                    description = description[:700] + "…"

                st.write(description)

            
            # Matching / verification reasons
            
            reasons = result.get("reasons", [])

            if reasons:
                st.caption(" · ".join(reasons))

            
            # Assessment information
            
            st.write(
                f'**Midsem:** '
                f'{course.get("midsem", "not recorded")} '
                f'| **Compre:** '
                f'{course.get("compre", "not recorded")}'
            )

            
            # Instructor
            

            if course.get("instructor_handout"):
                st.write(
                    "**Instructor:**",
                    course["instructor_handout"],
                )

          # Attendance


            if course.get("attendance_policy"):
                attendance = course["attendance_policy"]

                if len(attendance) > 500:
                    attendance = attendance[:500] + "…"

                st.caption(
                    "**Attendance:** " + attendance
                )


            # Evaluation


            if course.get("evaluation_scheme_raw"):
                evaluation = course["evaluation_scheme_raw"]

                if len(evaluation) > 700:
                    evaluation = evaluation[:700] + "…"

                st.caption(
                    "**Evaluation:** " + evaluation
                )


            # Make-up policy


            if course.get("makeup_policy"):
                makeup = course["makeup_policy"]

                if len(makeup) > 500:
                    makeup = makeup[:500] + "…"

                st.caption(
                    "**Make-up:** " + makeup
                )


            # Source handout


            if course.get("handout_source_files"):
                st.caption(
                    "Part II handout: "
                    + ", ".join(course["handout_source_files"])
                )


    # Schedule result


    if schedule_found:
        st.success(
            "A clash-free section combination was found "
            "for the displayed recommendations."
        )
    else:
        st.warning(
            "No complete clash-free section combination "
            "was found for the displayed set."
        )


   # Agent trace


    with st.expander("Agent trace"):

        for trace_item in trace:
            st.write(
                "**" + trace_item.name + "**",
                trace_item.output,
            )



# Course explorer


st.subheader("Course explorer")

search = st.text_input(
    "Search processed timetable",
    placeholder="computer architecture",
)


if search:

    search_lower = search.lower()

    hits = [
        course
        for course in r.courses
        if search_lower
        in (
            course["course_code"]
            + " "
            + course["title"]
            + " "
            + course.get("description", "")
        ).lower()
    ]

    explorer_rows = [
        {
            "Code": course["course_code"],
            "Title": course["title"],
            "Units": course["units"],
            "Category": course["category"],
            "Midsem": course.get("midsem"),
            "Compre": course.get("compre"),
        }
        for course in hits[:50]
    ]

    st.dataframe(
        explorer_rows,
        use_container_width=True,
    )



# Data provenance


with st.expander("Verification / data provenance"):

    st.write(
        "Course-specific attendance, evaluation and make-up "
        "information is taken from the supplied Part II handouts "
        "when stated."
    )

    st.write(
        "If a handout does not state a requested property, "
        "the app marks that property as unverified rather than "
        "inventing it."
    )

    st.write(
        "Student transcript data is not supplied, so requirement "
        "completion must be entered manually in the profile."
    )
