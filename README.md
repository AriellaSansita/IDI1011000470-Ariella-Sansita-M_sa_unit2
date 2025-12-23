# IDI1011000470-Ariella-Sansita-M

# MedTimer Daily Medicine Companion

# Candidate Name - Ariella Sansita M

# Candidate Registration Number - 1000470

# CRS Name: Artificial Intelligence

# Course Name - Python Programming

# School name - Birla Open Minds International School, Kollur

# Summative Assessment

# MedTimer

# Project Overview
MedTimer is a Python-based interactive daily medicine companion designed to support elderly users and individuals managing chronic conditions by simplifying medication routines. Built using Streamlit, the application allows users to add and track medicines with scheduled times, view a clear color-coded checklist indicating taken, upcoming, or missed doses, and monitor their adherence through a weekly adherence score. To make the experience encouraging rather than clinical, MedTimer integrates Turtle graphics that display positive visual feedback, such as smiley faces or trophies, when adherence is high. With its calm design, large fonts, and intuitive interface, the project focuses on improving medication consistency, reducing anxiety, and promoting better health outcomes through accessible and user-friendly technology.

# Integration Details

- Medicines and dose times are stored using st.session_state.
- The datetime module determines whether a dose is taken, upcoming, or missed.
- Weekly adherence score is calculated automatically using scheduled vs taken doses.
- Turtle graphics display a smiley or trophy when adherence is high.
- ReportLab generates a weekly downloadable PDF report.
- Streamlit updates the UI in real time as users mark medicines taken.

## Features

- Add, edit, and delete medicines
- Set multiple dose times per day
- Color-coded status:
  - Green = Taken
  - Yellow = Upcoming
  - Red = Missed
- Weekly adherence score
- Motivational messages
- Friendly turtle graphic
- Downloadable weekly PDF report

## Technologies Used

- Python
- Streamlit
- datetime
- reportlab
- Pillow (for graphics)

## Deployment Instructions

The app was deployed on Streamlit Cloud by connecting the GitHub repository, selecting app.py as the main entry file, and installing dependencies from requirements.txt. Streamlit automatically built and hosted the application online.

## Turtle graphics could not be displayed in the deployed Streamlit. Therefore, emojis were used for encouragement is shown in the screenshots. The Turtle code is included in FILE to show the intended design. 
<img width="677" height="262" alt="Screenshot 2025-12-23 at 9 17 39 PM" src="https://github.com/user-attachments/assets/4ddb6c9c-1f5a-41a5-8858-d6bd5db1dae3" />

## Live App Link
https://idi1011000470-ariella-sansita-msaunit2-tvk2l34ju2brshjnfn2fjo.streamlit.app/

# App Screenshots:
<img width="1390" height="667" alt="Screenshot 2025-12-23 at 9 48 02 PM" src="https://github.com/user-attachments/assets/6827c768-9025-44b9-ac07-4494a8e244e6" />
<img width="1361" height="683" alt="Screenshot 2025-12-23 at 9 48 47 PM" src="https://github.com/user-attachments/assets/6e377808-7ac7-4380-8fc1-8b5dda22399e" />
<img width="1409" height="555" alt="Screenshot 2025-12-23 at 9 49 05 PM" src="https://github.com/user-attachments/assets/d5d87608-3b43-4b24-ad40-43017c95e5f7" />
