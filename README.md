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


## Live App Link
https://idi1011000470-ariella-sansita-msaunit2-tvk2l34ju2brshjnfn2fjo.streamlit.app/
