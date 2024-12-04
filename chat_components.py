import json
import time
import streamlit as st
from openai import OpenAI
from constants import OPENAI_INITIAL_CONVERSATION
from keywords import (
    get_user_keyphrases,
    rank_projects_by_keyphrases,
    rank_experiences_by_keyphrases,
)


@st.cache_resource()
def get_cached_openai_service():
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


def chat_back_button(id=""):
    if st.button("Edit Resume", key=f"chat_back_button_{id}"):
        st.session_state.is_chat_open = False
        st.session_state.display_conversation = []
        st.session_state.gpt_conversation = []
        st.rerun()


def openai_chat():
    if not "intro" in st.session_state:
        st.error("Something went wrong. Please reload the page")
        return

    if not "keywords" in st.session_state:
        st.session_state.keywords = []

    if not "suggestions" in st.session_state:
        st.session_state.suggestions = []

    if not "suggested_prompt_used" in st.session_state:
        st.session_state.suggested_prompt_used = ""

    name = st.session_state.intro["name"]
    email = st.session_state.intro["email"]
    summary = st.session_state.intro["summary"]
    experience = st.session_state.experience
    projects = st.session_state.projects
    education = st.session_state.education

    # Initializating
    open_ai = get_cached_openai_service()
    if "message_count" not in st.session_state:
        st.session_state.message_count = 0

    if "display_conversation" not in st.session_state:
        st.session_state.display_conversation = []

    if (
        "gpt_conversation" not in st.session_state
        or len(st.session_state.gpt_conversation) == 0
    ):
        st.session_state.relevant_projects = []
        st.session_state.relevant_experience = []
        st.session_state.gpt_conversation = OPENAI_INITIAL_CONVERSATION
        st.session_state.gpt_conversation.append(
            {
                "role": "system",
                "content": f"You are {name}'s Resume Assistant. Make conversation sound natural, always attribute to {name}. IMPORTANT: Follow the model of the previous conversation. You are a chat assistant LLM whose objective is to ingest the resume of {name} and make conversation with the user to inform them about {name}'s qualifications. Ensure responses are easy to understand, sound natural, and provide details and reasoning behind each response. For example, when providing context about {name}'s experience, explain what they did at each job and why that makes them qualified. Keep responses concise when possible and format with markdown to make the text readable. Include direct references to the experiences, projects, and education provided to help show how {name} is qualified. Note: Do not generate information outside of the context provided. Stick strongly to the experience, projects, education, and introduction given in the context provided! If you do not know the answer to a question, say that you do not know, and to contact {name} directly using the email: {email}. With each message, generate 3 suggested questions to 1) dive deeper into the current project or experience OR 2) Explore other similar/relevant projects and experience. You must respond in JSON format. \n\nHere is the context about {name}. Introduction: {summary}. Work Experience: {experience}. Projects: {projects}. Education: {education}. You MUST use this information only. Do not add or remove information from what I have provided. To start, introduce yourself like this: Hello! I am [name]'s Resume Assistant! Feel free to ask me any questions about [name]'s work experience, projects, education, and general qualifications. If you aren't sure what to ask, try these:\n",
                # 1. Give me a timeline of {name}'s work experience. \n 2. What is {name} most experienced with? \n 3. Give me examples of {name}'s leadership experience.
            },
        )

        completion = open_ai.chat.completions.create(
            model="gpt-3.5-turbo",
            response_format={"type": "json_object"},
            messages=st.session_state.gpt_conversation,
        )
        response = completion.choices[0].message.content
        response_obj = json.loads(response)
        message = response_obj["message"]
        st.session_state.suggestions = response_obj["suggestions"]

        st.session_state.gpt_conversation.append(
            {"role": "assistant", "content": response}
        )
        st.session_state.display_conversation.append(
            {"role": "assistant", "content": message}
        )

    with st.sidebar:
        st.subheader("Relevant Projects (from keywords)")
        with st.container():
            for rank, project in enumerate(st.session_state.relevant_projects, start=1):
                with st.expander(f"{rank}. {project['title']}"):
                    st.markdown(f"## {project['title']}")
                    st.markdown(
                        f"#### {project['organization']} (*{project['start']} to {project['end']}*)"
                    )
                    st.markdown(project["description"])
        st.divider()
        st.subheader("Relevant Experience (from keywords)")
        with st.container():
            for rank, experience in enumerate(
                st.session_state.relevant_experience, start=1
            ):
                with st.expander(
                    f"{rank}. {experience['title']} @ {experience['company']}"
                ):
                    st.markdown(f"## {experience['title']}")
                    st.markdown(
                        f"#### {experience['company']} (*{experience['start']} to {experience['end']}*)"
                    )
                    st.markdown(experience["description"])

    # Displaying and updating chat
    st.title("Ask My Resume")

    st.info(
        "#### Thank you for visiting, I'd love your feedback! \n *Please reach out to me at alexanderzhu07@gmail.com with any comments or feedback.*  \n\n **NOTE: This application is a prototype and is still in development.** To keep the project free, users are currently limited to 10 messages."
    )

    for message in st.session_state.display_conversation:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_placeholder = st.empty()
    assistant_placeholder = st.empty()
    suggestions_placeholder = st.empty()

    if st.session_state.suggestions:
        render_suggestions(
            suggestions_placeholder, 3 * len(st.session_state.display_conversation)
        )

    # React to user input
    if st.session_state.message_count > 10:
        st.warning(
            "You have passed your limit of 10 messages. In order to keep this service free, there is a 10 message limit per user. Please contact alexanderzhu07@gmail.com with any questions."
        )

    else:
        prompt = st.chat_input(f"Ask me about {name}!", max_chars=200)
        if st.session_state.suggested_prompt_used or prompt:
            suggestions_placeholder.empty()
            st.session_state.message_count += 1

            # If one of the suggestion buttons was used, that prompt takes priority
            if st.session_state.suggested_prompt_used:
                prompt = st.session_state.suggested_prompt_used
                st.session_state.suggested_prompt_used = ""

            with user_placeholder:
                st.chat_message("user").markdown(prompt)

            st.session_state.display_conversation.append(
                {"role": "user", "content": prompt}
            )
            st.session_state.gpt_conversation.append(
                {"role": "user", "content": prompt}
            )

            with assistant_placeholder:
                with st.spinner("Processing..."):
                    # display user keywords
                    st.session_state.keywords = get_user_keyphrases(
                        prompt, st.session_state.keywords
                    )

                    # Send message to Open AI
                    completion = open_ai.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=st.session_state.gpt_conversation,
                    )

                    response = completion.choices[0].message.content
                    response_obj = json.loads(response)
                    message = response_obj["message"]
                    st.session_state.suggestions = response_obj["suggestions"]

                    # List the most relevant projects and experiences
                    st.session_state.relevant_projects = rank_projects_by_keyphrases(
                        st.session_state.projects, st.session_state.keywords
                    )[:3]

                    st.session_state.relevant_experience = (
                        rank_experiences_by_keyphrases(
                            st.session_state.experience, st.session_state.keywords
                        )[:3]
                    )

            # Display assistant response in chat message container
            full_msg = ""
            with assistant_placeholder:
                for word in message.split(" "):
                    full_msg += word + " "
                    time.sleep(0.05)
                    st.chat_message("assistant").markdown(full_msg)

            # Add assistant response to chat history
            st.session_state.display_conversation.append(
                {"role": "assistant", "content": message}
            )
            st.session_state.gpt_conversation.append(
                {"role": "assistant", "content": response}
            )

            st.rerun()


def render_suggestions(suggestions_placeholder, start=0):
    with suggestions_placeholder:
        with st.container():
            for i, suggestion in enumerate(st.session_state.suggestions, start=start):
                if st.button(
                    suggestion,
                    key=f"suggestion_{i}",
                    use_container_width=True,
                    type="secondary",
                ):
                    st.session_state.suggested_prompt_used = suggestion
