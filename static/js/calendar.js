document.addEventListener("DOMContentLoaded", () => {
    const bookingWrapper = document.querySelector(".booking-wrapper");
    const bookingConfigElement = document.getElementById("booking-config");
    let bookingConfig = {};

    if (bookingConfigElement) {
        try {
            bookingConfig = JSON.parse(bookingConfigElement.textContent);
        } catch (error) {
            bookingConfig = {};
        }
    }

    const calendarDays = document.getElementById("calendarDays");
    const monthDisplay = document.getElementById("monthDisplay");
    const prevBtn = document.getElementById("prevMonth");
    const nextBtn = document.getElementById("nextMonth");
    const availabilityHeader = document.getElementById("availabilityHeader");
    const selectedDateLabel = document.getElementById("selectedDateLabel");
    const appointmentDateInput = document.getElementById("appointmentDateInput");
    const appointmentTimeInput = document.getElementById("appointmentTimeInput");
    const selectedTimeLabel = document.getElementById("selectedTimeLabel");
    const timesList = document.getElementById("timesList");
    const confirmBookingBtn = document.getElementById("confirmBookingBtn");
    const timesNav = document.getElementById("timesNav");
    const timePrevBtn = document.getElementById("timePrevBtn");
    const timeNextBtn = document.getElementById("timeNextBtn");
    const timesNavLabel = document.getElementById("timesNavLabel");
    const availableSlotsByDate = bookingConfig.availableSlotsByDate || {};
    const pageSize = 4;
    let activeSlots = [];
    let timePage = 0;

    const revealNodes = document.querySelectorAll(".reveal");
    if ("IntersectionObserver" in window && revealNodes.length) {
        const revealObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add("revealed");
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });
        revealNodes.forEach((node) => revealObserver.observe(node));
    } else {
        revealNodes.forEach((node) => node.classList.add("revealed"));
    }

    const parallaxItems = Array.from(document.querySelectorAll("[data-parallax]"));
    if (parallaxItems.length) {
        let ticking = false;
        const paintParallax = () => {
            const scrollY = window.scrollY || window.pageYOffset || 0;
            parallaxItems.forEach((node) => {
                const speed = Number(node.getAttribute("data-parallax")) || 0;
                node.style.transform = `translate3d(0, ${scrollY * speed}px, 0)`;
            });
            ticking = false;
        };

        window.addEventListener("scroll", () => {
            if (!ticking) {
                window.requestAnimationFrame(paintParallax);
                ticking = true;
            }
        }, { passive: true });

        paintParallax();
    }

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const initialDateParts = ((bookingWrapper && bookingWrapper.dataset.initialDate) || "").split("-");
    const initialDate = initialDateParts.length === 3
        ? new Date(Number(initialDateParts[0]), Number(initialDateParts[1]) - 1, Number(initialDateParts[2]))
        : new Date(today.getFullYear(), today.getMonth(), today.getDate());

    let viewDate = new Date(initialDate.getFullYear(), initialDate.getMonth(), 1);
    let selectedDate = initialDate;

    function formatLabel(dateValue) {
        return dateValue.toLocaleDateString("en-US", {
            weekday: "long",
            month: "long",
            day: "numeric",
            year: "numeric",
        });
    }

    function formatISO(dateValue) {
        const year = dateValue.getFullYear();
        const month = String(dateValue.getMonth() + 1).padStart(2, "0");
        const day = String(dateValue.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function updateSelectedDate(dateValue) {
        selectedDate = new Date(dateValue.getFullYear(), dateValue.getMonth(), dateValue.getDate());
        const label = formatLabel(selectedDate);
        availabilityHeader.textContent = `Available time for ${label}`;
        selectedDateLabel.textContent = label;
        appointmentDateInput.value = formatISO(selectedDate);
        renderTimeSlots(appointmentDateInput.value);
        renderCalendar();
    }

    function renderTimeSlots(dateIso) {
        activeSlots = availableSlotsByDate[dateIso] || [];
        timePage = 0;
        renderTimeSlotsPage();
    }

    function renderTimeSlotsPage() {
        timesList.innerHTML = "";
        const availableSlots = activeSlots;

        if (availableSlots.length === 0) {
            const emptyState = document.createElement("div");
            emptyState.className = "times-empty";
            emptyState.textContent = "No available times for this date.";
            timesList.appendChild(emptyState);
            appointmentTimeInput.value = "";
            selectedTimeLabel.textContent = "Unavailable";
            confirmBookingBtn.disabled = true;
            confirmBookingBtn.classList.add("is-disabled");
            if (timesNav) {
                timesNav.style.display = "none";
            }
            return;
        }

        const totalPages = Math.ceil(availableSlots.length / pageSize);
        const startIndex = timePage * pageSize;
        const endIndex = Math.min(startIndex + pageSize, availableSlots.length);
        const visibleSlots = availableSlots.slice(startIndex, endIndex);

        if (timesNav) {
            timesNav.style.display = totalPages > 1 ? "flex" : "none";
        }
        if (timesNavLabel) {
            timesNavLabel.textContent = `${timePage + 1}/${totalPages}`;
        }
        if (timePrevBtn) {
            timePrevBtn.disabled = timePage <= 0;
        }
        if (timeNextBtn) {
            timeNextBtn.disabled = timePage >= totalPages - 1;
        }

        visibleSlots.forEach((time, index) => {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "time-card";
            if (index === 0) {
                button.classList.add("selected-time");
            }
            button.dataset.time = time;
            button.textContent = time;
            button.addEventListener("click", () => {
                timesList.querySelectorAll(".time-card").forEach((item) => item.classList.remove("selected-time"));
                button.classList.add("selected-time");
                appointmentTimeInput.value = time;
                selectedTimeLabel.textContent = time;
            });
            timesList.appendChild(button);
        });

        appointmentTimeInput.value = visibleSlots[0];
        selectedTimeLabel.textContent = visibleSlots[0];
        confirmBookingBtn.disabled = false;
        confirmBookingBtn.classList.remove("is-disabled");
    }

    function renderCalendar() {
        const year = viewDate.getFullYear();
        const month = viewDate.getMonth();
        const monthName = viewDate.toLocaleString("default", { month: "long" });
        monthDisplay.textContent = `${monthName} ${year}`;
        calendarDays.innerHTML = "";

        const firstDay = new Date(year, month, 1).getDay();
        const totalDays = new Date(year, month + 1, 0).getDate();

        for (let i = 0; i < firstDay; i += 1) {
            const emptyDiv = document.createElement("div");
            emptyDiv.className = "empty-day";
            calendarDays.appendChild(emptyDiv);
        }

        for (let day = 1; day <= totalDays; day += 1) {
            const dateObj = new Date(year, month, day);
            const dayElement = document.createElement("button");
            dayElement.type = "button";
            dayElement.textContent = day;
            dayElement.classList.add("calendar-day");

            if (dateObj.toDateString() === selectedDate.toDateString()) {
                dayElement.classList.add("active-day");
            }

            if (dateObj < today) {
                dayElement.classList.add("past-day");
                dayElement.disabled = true;
            } else if ((availableSlotsByDate[formatISO(dateObj)] || []).length === 0) {
                dayElement.classList.add("unavailable-day");
                dayElement.disabled = true;
            } else {
                dayElement.addEventListener("click", () => updateSelectedDate(dateObj));
            }

            calendarDays.appendChild(dayElement);
        }
    }

    prevBtn.addEventListener("click", () => {
        const candidate = new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1);
        const startOfCurrentMonth = new Date(today.getFullYear(), today.getMonth(), 1);
        if (candidate >= startOfCurrentMonth) {
            viewDate = candidate;
            renderCalendar();
        }
    });

    nextBtn.addEventListener("click", () => {
        viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1);
        renderCalendar();
    });

    if (timePrevBtn) {
        timePrevBtn.addEventListener("click", () => {
            if (timePage <= 0) {
                return;
            }
            timePage -= 1;
            renderTimeSlotsPage();
        });
    }

    if (timeNextBtn) {
        timeNextBtn.addEventListener("click", () => {
            const totalPages = Math.ceil(activeSlots.length / pageSize);
            if (timePage >= totalPages - 1) {
                return;
            }
            timePage += 1;
            renderTimeSlotsPage();
        });
    }

    updateSelectedDate(selectedDate);
});

