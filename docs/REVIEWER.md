# SchedTalk Reviewer

## 1. Project Overview

SchedTalk is a Flask-based medical appointment system. It has:

- a public home page
- login and signup for users
- a booking page for appointments
- a chatbot that can check schedule availability and create bookings
- an admin dashboard for calendar, patients, and settings

The system uses two storage sources:

- MySQL for user accounts
- `data/clinic_data.json` for patients and appointments

---

## 2. Main Technologies Used

- Python
- Flask
- Flask-MySQLdb
- HTML, CSS, JavaScript
- JSON file storage
- SMTP/Gmail for Contact Us email sending

---

## 3. File Structure

Important files:

- [app.py](C:/Users/bagsi/OneDrive/Desktop/Capstone/app.py)
- [home.html](C:/Users/bagsi/OneDrive/Desktop/Capstone/templates/home.html)
- [booking.html](C:/Users/bagsi/OneDrive/Desktop/Capstone/templates/booking.html)
- [home.js](C:/Users/bagsi/OneDrive/Desktop/Capstone/static/js/home.js)
- [calendar.js](C:/Users/bagsi/OneDrive/Desktop/Capstone/static/js/calendar.js)
- [clinic_data.json](C:/Users/bagsi/OneDrive/Desktop/Capstone/data/clinic_data.json)

---

## 4. How The Database Connection Works

The database connection is inside [app.py](C:/Users/bagsi/OneDrive/Desktop/Capstone/app.py).

```python
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "schedtalk_db"

mysql = MySQL(app)
```

### Explanation

- `MYSQL_HOST` tells Flask where MySQL is running.
- `MYSQL_USER` is the MySQL username.
- `MYSQL_PASSWORD` is the MySQL password.
- `MYSQL_DB` is the database name.
- `MySQL(app)` activates the connection for the Flask app.

### What Is Stored In MySQL

The `users` table stores:

- username
- password
- email
- role
- full_name
- phone
- age
- gender

### Functions Related To The Database

- `fetch_user_by_username(username)`
- `fetch_user_by_email(email)`
- `ensure_user_profile_columns()`

### Why `ensure_user_profile_columns()` Is Important

This function checks whether extra columns already exist in the `users` table. If not, it adds them automatically.

That means the project can still work even if the original table was missing:

- `full_name`
- `phone`
- `age`
- `gender`

---

## 5. How Appointments And Patients Are Stored

Users are stored in MySQL, but appointments and patients are stored in:

- [clinic_data.json](C:/Users/bagsi/OneDrive/Desktop/Capstone/data/clinic_data.json)

### Related Variables

In [app.py](C:/Users/bagsi/OneDrive/Desktop/Capstone/app.py):

- `PATIENTS`
- `APPOINTMENTS`
- `DATA_FILE`

### Related Functions

- `ensure_data_file()`
- `load_data()`
- `save_data()`

### Flow

1. The app checks if `clinic_data.json` exists.
2. If not, it creates the file.
3. `load_data()` loads patients and appointments into memory.
4. When a booking or update happens, `save_data()` writes the new data back to the JSON file.

---

## 6. How Signup And Login Work

### Signup Flow

Route:

- `@app.route("/signup", methods=["POST"])`

### Steps

1. User fills in the signup form in [home.html](C:/Users/bagsi/OneDrive/Desktop/Capstone/templates/home.html).
2. The form sends data to `/signup`.
3. Flask checks if the email already exists using `fetch_user_by_email(email)`.
4. If the email is already registered, the page redirects back with `signup_error`.
5. If not, Flask inserts the new user into MySQL.
6. Session values are stored.
7. The homepage shows a success modal with the generated username.

### Username Generation

The username is created automatically:

```python
username = f"{fname.lower()}{lname[:2].lower()}"
```

Example:

- First name: `Jovan`
- Last name: `Bonifacio`
- Username: `jovanbo`

### Login Flow

Route:

- `@app.route("/login", methods=["POST"])`

### Steps

1. User enters username and password.
2. Flask finds the user through `fetch_user_by_username(username)`.
3. Password is checked.
4. If correct, session values are saved.
5. If the role is `admin`, user is redirected to admin dashboard.
6. If the role is `user`, user is redirected to homepage.

### Note

There is also a hard-coded admin fallback:

- username: `admin01`
- password: `0123`

---

## 7. How Scheduling Works

Scheduling is handled by the booking page and the appointment helper functions.

### Main Booking Routes

- `@app.route("/booking")`
- `@app.route("/booking", methods=["POST"])`

### Important Functions

- `build_booking_calendar_data()`
- `get_available_slots_for_date(appointment_date)`
- `is_time_slot_taken(appointment_date, appointment_time)`
- `create_appointment_booking(...)`

### Booking Time Slots

Defined in [app.py](C:/Users/bagsi/OneDrive/Desktop/Capstone/app.py):

```python
BOOKING_TIME_SLOTS = ["08:00 AM", "10:00 AM", "01:00 PM", "03:00 PM"]
```

### How The System Prevents Double Booking

The function `is_time_slot_taken()` checks whether the selected date and time already exist in `APPOINTMENTS`.

If the slot is already used, the booking is rejected.

### Booking Page Flow

1. User opens [booking.html](C:/Users/bagsi/OneDrive/Desktop/Capstone/templates/booking.html).
2. Flask sends available slots by date to the page.
3. [calendar.js](C:/Users/bagsi/OneDrive/Desktop/Capstone/static/js/calendar.js) renders the calendar.
4. User selects a date.
5. JavaScript updates the available times.
6. User fills in contact info and appointment type.
7. Form submits to `/booking`.
8. Flask checks whether the slot is still available.
9. If available, `create_appointment_booking()` saves the appointment.
10. The appointment becomes visible in admin calendar and dashboard.

### What Happens Inside `create_appointment_booking()`

This function:

- checks if the time slot is available
- adds a new item to `APPOINTMENTS`
- updates or creates the matching patient record
- saves everything to `clinic_data.json`

---

## 8. How The Chatbot Works

The chatbot logic is mainly in:

- [home.js](C:/Users/bagsi/OneDrive/Desktop/Capstone/static/js/home.js)

The backend chatbot APIs are in:

- [app.py](C:/Users/bagsi/OneDrive/Desktop/Capstone/app.py)

### Chatbot UI Flow

On the homepage:

- chatbot icon opens the chatbot panel
- quick action buttons allow:
  - checking available schedules
  - booking appointments

### Chatbot Backend Routes

- `/api/availability`
- `/api/chatbot/book`

### `/api/availability`

Purpose:

- returns available slots for one date
- or returns upcoming availability

Example behavior:

- if user asks a specific date, it returns slots for that date
- if user asks generally, it returns the next available schedules

### `/api/chatbot/book`

Purpose:

- creates an appointment through chatbot conversation

The route checks:

- `appointment_date`
- `appointment_time`
- `appointment_type`

If complete and valid, it calls:

- `create_appointment_booking(...)`

---

## 9. How The Chatbot Understands Messages

Inside [home.js](C:/Users/bagsi/OneDrive/Desktop/Capstone/static/js/home.js), the chatbot uses helper functions to understand user input.

### Important Functions

- `detectAppointmentTypeFromText(text)`
- `parseDateFromText(text)`
- `parseTimeFromText(text)`
- `parseTimeWindowFromText(text)`
- `extractBookingDetails(text)`
- `validateBookingDetails(details)`

### What These Functions Do

#### `detectAppointmentTypeFromText(text)`

Finds the appointment type from keywords like:

- dental
- pediatric
- follow up
- consultation

#### `parseDateFromText(text)`

Reads different date formats such as:

- `2026-04-18`
- `04/18/2026`
- `April 18 2026`
- `tomorrow`
- `next monday`

#### `parseTimeFromText(text)`

Reads time formats like:

- `10:00 AM`
- `3 PM`

#### `parseTimeWindowFromText(text)`

Converts general words into schedule times:

- morning -> `08:00 AM`
- afternoon -> `01:00 PM`
- evening -> `03:00 PM`

#### `extractBookingDetails(text)`

Collects:

- appointment type
- date
- time
- notes

from the user message.

---

## 10. Chatbot Booking Conversation Flow

### Step-by-Step

1. User opens chatbot.
2. If not logged in, chatbot asks the user to log in first.
3. If logged in, chatbot can:
   - show availability
   - start booking
4. `startBookingFlow(message)` extracts initial details from the message.
5. If something is missing, chatbot asks only for the missing details.
6. When enough details are collected, `submitChatbotBooking(details)` sends them to `/api/chatbot/book`.
7. Flask saves the appointment and returns success.
8. Chatbot shows the booking confirmation in the chat panel.

### Why This Is Good

The chatbot does not require the user to fill everything at once. It can collect partial details and continue the conversation.

---

## 11. How The Calendar UI Works

The booking calendar frontend is in:

- [calendar.js](C:/Users/bagsi/OneDrive/Desktop/Capstone/static/js/calendar.js)

### Important Functions

- `renderCalendar()`
- `renderTimeSlots(dateIso)`
- `updateSelectedDate(dateValue)`

### Flow

1. The page reads `availableSlotsByDate` from JSON embedded in the template.
2. `renderCalendar()` builds the month view.
3. Past days are disabled.
4. Dates with no available slots are disabled.
5. When a date is clicked, `updateSelectedDate()` updates:
   - selected date label
   - hidden appointment date input
   - available time buttons
6. When a time is clicked, the hidden appointment time input is updated.

---

## 12. How The Admin Calendar Works

Route:

- `@app.route("/admin/calendar", methods=["GET", "POST"])`

### Functions Used

- `appointment_shows_in_calendar(appointment)`
- `find_appointment(appointment_id)`

### Current Behavior

The admin calendar now only shows:

- `Pending`
- `Scheduled`

It no longer shows:

- `Completed`
- `Cancelled`

This helps keep the calendar clean while older records still remain saved in the JSON file.

---

## 13. How Contact Us Works

Route:

- `@app.route("/contact", methods=["POST"])`

### Flow

1. User must be logged in first.
2. User fills out Contact Us form.
3. Flask validates the fields.
4. `send_contact_email(name, email, message)` sends the email using SMTP.
5. If successful, the homepage shows a success modal.
6. If mail setup is missing or invalid, the page shows an error.

### Mail Configuration

Stored in [`.env`](C:/Users/bagsi/OneDrive/Desktop/Capstone/.env):

- `SCHEDTALK_MAIL_SERVER`
- `SCHEDTALK_MAIL_PORT`
- `SCHEDTALK_MAIL_USE_SSL`
- `SCHEDTALK_MAIL_USERNAME`
- `SCHEDTALK_MAIL_PASSWORD`
- `SCHEDTALK_CONTACT_RECIPIENT`

---

## 14. Possible Questions In Defense Or Review

### Chatbot

- How does the chatbot understand user messages?
- How do you extract date, time, and appointment type from text?
- What happens if the slot is already taken?
- Why do users need to log in before chatbot booking?

### Scheduling

- How do you prevent double booking?
- How are available slots generated?
- Why are past dates disabled?
- How are appointments saved?

### Database

- Why are users stored in MySQL while appointments are in JSON?
- How does Flask connect to MySQL?
- What is the purpose of `ensure_user_profile_columns()`?
- What data is stored in session after login?

### Admin

- Why are completed and cancelled appointments hidden from the calendar?
- Where can old appointment data still be found?
- How are patient records updated after booking?

---

## 15. Simple Summary

### Chatbot

The chatbot works by reading user messages with JavaScript, extracting booking details, checking availability through Flask API routes, and saving confirmed bookings into the appointment data.

### Scheduling

The scheduling system uses fixed time slots, checks for conflicts, disables unavailable dates, and saves successful bookings to the appointment list and patient list.

### Database Connection

The app connects to MySQL through Flask-MySQLdb for account storage, while patient and appointment records are saved in a local JSON file.

---

## 16. Suggested Short Oral Explanation

You can say this in class or defense:

> Our system uses Flask as the backend. We connected MySQL for user accounts, while appointments and patient records are stored in a JSON file. For scheduling, the system checks available dates and fixed time slots, then prevents double booking before saving the appointment. For the chatbot, we used JavaScript on the homepage to read the user’s message, extract the appointment type, date, and time, then call Flask API routes to check availability or create a booking.

