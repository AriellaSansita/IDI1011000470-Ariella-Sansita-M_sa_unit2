# IDI1011000470-Ariella-Sansita-M

# MedTimer Daily Medicine Companion

# Candidate Name - Ariella Sansita M

# Candidate Registration Number - 1000470

# CRS Name: Artificial Intelligence

# Course Name - Python Programming

# School name - Birla Open Minds International School, Kollur

# Summative Assessment

# MedTimer

MedTimer provides an easy-to-use medicine tracking system where users can log medicines, check daily dose status, view weekly adherence, and download a summary report. The interface is designed to be senior-friendly with large fonts, color-coded reminders, and supportive Turtle graphics.

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

## How to Run Locally

1. Install the required packages:

```bash
pip install -r requirements.txt
```

2. Run the app:

```bash
streamlit run app.py
```

## Live App Link
https://idi1011000470-ariella-sansita-msaunit2-tvk2l34ju2brshjnfn2fjo.streamlit.app/
