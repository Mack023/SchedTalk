document.addEventListener("DOMContentLoaded", function () {
    const loginModal = document.getElementById("loginModal");
    const closeLogin = document.getElementById("closeLogin");
    const openLoginTriggers = document.querySelectorAll("#loginBtn, .open-login");
    const signupModal = document.getElementById("signupModal");
    const otpModal = document.getElementById("otpModal");
    const closeSignup = document.getElementById("closeSignup");
    const closeOtp = document.getElementById("closeOtp");
    const openSignupFromLoginBtn = document.getElementById("openSignupBtn");
    const backToLoginBtn = document.getElementById("backToLogin");
    const backToLoginFromOtpBtn = document.getElementById("backToLoginFromOtp");
    const contactSuccessModal = document.getElementById("contactSuccessModal");
    const closeContactSuccess = document.getElementById("closeContactSuccess");
    const contactSuccessOk = document.getElementById("contactSuccessOk");
    const signupSuccessModal = document.getElementById("signupSuccessModal");
    const closeSignupSuccess = document.getElementById("closeSignupSuccess");
    const signupSuccessOk = document.getElementById("signupSuccessOk");

    const chatbotToggle = document.getElementById("chatbotToggle");
    const chatbotPanel = document.getElementById("chatbotPanel");
    const chatbotClose = document.getElementById("chatbotClose");
    const chatbotMessages = document.getElementById("chatbotMessages");
    const chatbotForm = document.getElementById("chatbotForm");
    const chatbotInput = document.getElementById("chatbotInput");
    const tryChatbotBtn = document.getElementById("tryChatbotBtn");
    const contactForm = document.getElementById("contactForm");
    const quickActionButtons = document.querySelectorAll(".quick-action");
    const openChatbotLinks = document.querySelectorAll(".open-chatbot");
    const isLoggedIn = Boolean(window.schedTalkIsLoggedIn);
    const chatbotProfile = window.schedTalkChatbotProfile || {};
    const modalCards = document.querySelectorAll(".login-modal .login-card");

    const menuContainer = document.querySelector(".menu-container");
    const menuButton = document.querySelector(".menu-icon");
    const pageHeader = document.querySelector("header");
    const logoNode = document.querySelector(".logo");

    if (menuButton && menuContainer) {
        menuButton.addEventListener("click", function (event) {
            event.stopPropagation();
            const willOpen = !menuContainer.classList.contains("is-open");
            menuContainer.classList.toggle("is-open", willOpen);
            menuButton.setAttribute("aria-expanded", willOpen ? "true" : "false");
        });

        document.addEventListener("click", function (event) {
            if (!menuContainer.contains(event.target)) {
                menuContainer.classList.remove("is-open");
                menuButton.setAttribute("aria-expanded", "false");
            }
        });
    }

    const revealNodes = document.querySelectorAll(".reveal");
    if ("IntersectionObserver" in window && revealNodes.length) {
        const revealObserver = new IntersectionObserver(function (entries, observer) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add("revealed");
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.15 });

        revealNodes.forEach(function (node) {
            revealObserver.observe(node);
        });
    } else {
        revealNodes.forEach(function (node) {
            node.classList.add("revealed");
        });
    }

    const parallaxItems = Array.from(document.querySelectorAll("[data-parallax]"));
    if (parallaxItems.length) {
        let ticking = false;

        function paintParallax() {
            const scrollY = window.scrollY || window.pageYOffset || 0;
            parallaxItems.forEach(function (node) {
                const speed = Number(node.getAttribute("data-parallax")) || 0;
                node.style.transform = "translate3d(0, " + (scrollY * speed) + "px, 0)";
            });
            ticking = false;
        }

        window.addEventListener("scroll", function () {
            if (!ticking) {
                window.requestAnimationFrame(paintParallax);
                ticking = true;
            }
        }, { passive: true });

        paintParallax();
    }

    if (pageHeader) {
        let navTicking = false;

        function paintNavParallax() {
            const scrollY = window.scrollY || window.pageYOffset || 0;
            const drift = Math.max(-8, Math.min(8, scrollY * -0.02));
            pageHeader.style.setProperty("--nav-bg-parallax", drift.toFixed(2) + "px");
            navTicking = false;
        }

        window.addEventListener("scroll", function () {
            if (!navTicking) {
                window.requestAnimationFrame(paintNavParallax);
                navTicking = true;
            }
        }, { passive: true });

        paintNavParallax();
    }

    if (pageHeader && logoNode) {
        pageHeader.addEventListener("mousemove", function (event) {
            const bounds = pageHeader.getBoundingClientRect();
            const xRatio = (event.clientX - bounds.left) / bounds.width;
            const yRatio = (event.clientY - bounds.top) / bounds.height;
            const shiftX = (xRatio - 0.5) * 2.4;
            const shiftY = (yRatio - 0.5) * 1.6;
            logoNode.style.transform = "translate3d(" + shiftX.toFixed(2) + "px, " + shiftY.toFixed(2) + "px, 0)";
        });

        pageHeader.addEventListener("mouseleave", function () {
            logoNode.style.transform = "translate3d(0, 0, 0)";
        });
    }

    const appointmentTypes = [
        "General Consultation",
        "Pediatric Consultation",
        "Dental Consultation",
        "Follow-up Consultation",
    ];

    const monthMap = {
        january: "01",
        february: "02",
        march: "03",
        april: "04",
        may: "05",
        june: "06",
        july: "07",
        august: "08",
        september: "09",
        october: "10",
        november: "11",
        december: "12",
        jan: "01",
        feb: "02",
        mar: "03",
        apr: "04",
        jun: "06",
        jul: "07",
        aug: "08",
        sep: "09",
        sept: "09",
        oct: "10",
        nov: "11",
        dec: "12",
    };

    const chatbotState = {
        awaitingBookingDetails: false,
        pendingBookingDate: "",
        pendingBookingTime: "",
        pendingBookingType: "",
        pendingBookingNotes: "",
        availableSlotsForSelectedDate: [],
        greeted: false,
        rememberedName: "",
        preferredTone: "warm",
        botMessageQueue: Promise.resolve(),
        typingIndicatorEl: null,
    };

    function showLogin() {
        otpModal.style.display = "none";
        signupModal.style.display = "none";
        loginModal.style.display = "flex";
        loginModal.classList.add("modal-open");
    }

    function showSignup() {
        otpModal.style.display = "none";
        loginModal.style.display = "none";
        signupModal.style.display = "flex";
        signupModal.classList.add("modal-open");
    }

    function showOtp() {
        loginModal.style.display = "none";
        signupModal.style.display = "none";
        otpModal.style.display = "flex";
        otpModal.classList.add("modal-open");
    }

    function hideAllModals() {
        loginModal.classList.remove("modal-open");
        signupModal.classList.remove("modal-open");
        if (otpModal) {
            otpModal.classList.remove("modal-open");
        }
        loginModal.style.display = "none";
        signupModal.style.display = "none";
        if (otpModal) {
            otpModal.style.display = "none";
        }
        if (contactSuccessModal) {
            contactSuccessModal.style.display = "none";
        }
        if (signupSuccessModal) {
            signupSuccessModal.style.display = "none";
        }
    }

    function showContactSuccess() {
        hideAllModals();
        if (contactSuccessModal) {
            contactSuccessModal.style.display = "flex";
        }
    }

    function showSignupSuccess() {
        hideAllModals();
        if (signupSuccessModal) {
            signupSuccessModal.style.display = "flex";
        }
    }

    openLoginTriggers.forEach(function (element) {
        element.addEventListener("click", function (e) {
            e.preventDefault();
            showLogin();
        });
    });

    if (openSignupFromLoginBtn) {
        openSignupFromLoginBtn.addEventListener("click", function (e) {
            e.preventDefault();
            showSignup();
        });
    }

    if (backToLoginBtn) {
        backToLoginBtn.addEventListener("click", function (e) {
            e.preventDefault();
            showLogin();
        });
    }

    if (closeLogin) {
        closeLogin.addEventListener("click", function () {
            loginModal.classList.remove("modal-open");
            loginModal.style.display = "none";
        });
    }

    if (closeSignup) {
        closeSignup.addEventListener("click", function () {
            signupModal.classList.remove("modal-open");
            signupModal.style.display = "none";
        });
    }

    if (closeOtp) {
        closeOtp.addEventListener("click", function () {
            otpModal.classList.remove("modal-open");
            otpModal.style.display = "none";
        });
    }

    modalCards.forEach(function (card) {
        card.addEventListener("mousemove", function (event) {
            const bounds = card.getBoundingClientRect();
            const x = event.clientX - bounds.left;
            const y = event.clientY - bounds.top;
            const rotateY = ((x / bounds.width) - 0.5) * 6;
            const rotateX = (0.5 - (y / bounds.height)) * 6;
            card.style.transform = "perspective(900px) rotateX(" + rotateX.toFixed(2) + "deg) rotateY(" + rotateY.toFixed(2) + "deg) translateZ(0)";
        });

        card.addEventListener("mouseleave", function () {
            card.style.transform = "perspective(900px) rotateX(0deg) rotateY(0deg) translateZ(0)";
        });
    });

    if (backToLoginFromOtpBtn) {
        backToLoginFromOtpBtn.addEventListener("click", function (e) {
            e.preventDefault();
            showLogin();
        });
    }

    if (closeContactSuccess) {
        closeContactSuccess.addEventListener("click", function () {
            contactSuccessModal.style.display = "none";
        });
    }

    if (contactSuccessOk) {
        contactSuccessOk.addEventListener("click", function () {
            contactSuccessModal.style.display = "none";
        });
    }

    if (closeSignupSuccess) {
        closeSignupSuccess.addEventListener("click", function () {
            signupSuccessModal.style.display = "none";
        });
    }

    if (signupSuccessOk) {
        signupSuccessOk.addEventListener("click", function () {
            signupSuccessModal.style.display = "none";
        });
    }

    window.addEventListener("click", function (e) {
        if (e.target === loginModal || e.target === signupModal || e.target === otpModal) {
            hideAllModals();
        }
    });

    if (window.schedTalkOtpRequired) {
        showOtp();
    } else if (window.schedTalkLoginRequired || window.schedTalkLoginError) {
        showLogin();
    }

    if (window.schedTalkContactSent) {
        showContactSuccess();
    }

    if (window.schedTalkSignupError) {
        showSignup();
    }

    if (window.schedTalkSignupSuccess) {
        showSignupSuccess();
    }

    function appendChatMessage(role, text) {
        const message = document.createElement("div");
        message.className = "chat-message " + (role === "bot" ? "bot-message" : "user-message");
        message.textContent = text;
        chatbotMessages.appendChild(message);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
    }

    function typingDelayForText(text) {
        const textLength = (text || "").length;
        return Math.max(350, Math.min(1300, 220 + textLength * 12));
    }

    function showTypingIndicator() {
        if (chatbotState.typingIndicatorEl) {
            return;
        }
        const indicator = document.createElement("div");
        indicator.className = "chat-message bot-message";
        indicator.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
        chatbotMessages.appendChild(indicator);
        chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
        chatbotState.typingIndicatorEl = indicator;
    }

    function hideTypingIndicator() {
        if (!chatbotState.typingIndicatorEl) {
            return;
        }
        chatbotState.typingIndicatorEl.remove();
        chatbotState.typingIndicatorEl = null;
    }

    function addChatMessage(role, text) {
        if (role !== "bot") {
            appendChatMessage(role, text);
            return;
        }

        chatbotState.botMessageQueue = chatbotState.botMessageQueue.then(async function () {
            showTypingIndicator();
            await new Promise(function (resolve) {
                setTimeout(resolve, typingDelayForText(text));
            });
            hideTypingIndicator();
            appendChatMessage("bot", text);
        });
    }

    function inferPreferredTone(message) {
        const normalized = (message || "").toLowerCase();
        if (
            normalized.includes("short answer") ||
            normalized.includes("just answer") ||
            normalized.includes("quick answer")
        ) {
            return "concise";
        }
        if (
            normalized.includes("anxious") ||
            normalized.includes("worried") ||
            normalized.includes("stress") ||
            normalized.includes("scared")
        ) {
            return "reassuring";
        }
        return "warm";
    }

    function rememberUserDetails(message) {
        const nameMatch = (message || "").match(/\b(?:my name is|i am|i'm)\s+([A-Za-z][A-Za-z\s'-]{1,30})\b/i);
        if (nameMatch) {
            chatbotState.rememberedName = nameMatch[1].trim();
        }
        chatbotState.preferredTone = inferPreferredTone(message);
    }

    function openChatbot() {
        if (!isLoggedIn) {
            addLoginRequiredPrompt();
            showLogin();
            return;
        }

        chatbotPanel.classList.add("is-open");
        chatbotPanel.setAttribute("aria-hidden", "false");
        chatbotInput.focus();

        if (!chatbotState.greeted) {
            chatbotState.greeted = true;
            const displayName = chatbotState.rememberedName || chatbotProfile.name || "";
            addChatMessage(
                "bot",
                "Hi" + (displayName ? " " + displayName : "") + ", I’m really glad you’re here. I can help with scheduling, booking, and general questions too."
            );
            addChatMessage(
                "bot",
                "Whenever you’re ready, tell me what you need. Example: Can you check available slots for 2026-04-18?"
            );
        }
    }

    function closeChatbotPanel() {
        chatbotPanel.classList.remove("is-open");
        chatbotPanel.setAttribute("aria-hidden", "true");
    }

    function addLoginRequiredPrompt() {
        if (!chatbotState.greeted) {
            chatbotState.greeted = true;
            addChatMessage("bot", "Please login first before using the chatbot.");
        }
    }

    function resetBookingFlow() {
        chatbotState.awaitingBookingDetails = false;
        chatbotState.pendingBookingDate = "";
        chatbotState.pendingBookingTime = "";
        chatbotState.pendingBookingType = "";
        chatbotState.pendingBookingNotes = "";
        chatbotState.availableSlotsForSelectedDate = [];
    }

    function normalizeAppointmentType(value) {
        const normalized = value.trim().toLowerCase();
        const match = appointmentTypes.find(function (type) {
            const shortType = type.toLowerCase().replace(" consultation", "");
            return (
                type.toLowerCase() === normalized ||
                shortType === normalized ||
                type.toLowerCase().includes(normalized) ||
                normalized.includes(shortType)
            );
        });
        return match || value.trim();
    }

    function detectAppointmentTypeFromText(text) {
        const normalized = text.toLowerCase();

        if (
            normalized.includes("dental") ||
            normalized.includes("tooth") ||
            normalized.includes("teeth") ||
            normalized.includes("gum") ||
            normalized.includes("oral") ||
            normalized.includes("cavity") ||
            normalized.includes("dentist")
        ) {
            return "Dental Consultation";
        }
        if (
            normalized.includes("pediatric") ||
            normalized.includes("pediatrician") ||
            normalized.includes("child") ||
            normalized.includes("kid") ||
            normalized.includes("baby") ||
            normalized.includes("infant") ||
            normalized.includes("children")
        ) {
            return "Pediatric Consultation";
        }
        if (
            normalized.includes("follow up") ||
            normalized.includes("follow-up") ||
            normalized.includes("followup") ||
            normalized.includes("return visit") ||
            normalized.includes("check again") ||
            normalized.includes("recheck") ||
            normalized.includes("review")
        ) {
            return "Follow-up Consultation";
        }
        if (
            normalized.includes("general consultation") ||
            normalized.includes("general checkup") ||
            normalized.includes("general check-up") ||
            normalized.includes("medical checkup") ||
            normalized.includes("medical check-up") ||
            normalized.includes("routine checkup") ||
            normalized.includes("routine check-up") ||
            normalized.includes("doctor checkup") ||
            normalized.includes("doctor check-up") ||
            normalized.includes("clinic visit") ||
            normalized.includes("see a doctor") ||
            normalized.includes("check my health") ||
            normalized.includes("checkup") ||
            normalized.includes("check-up") ||
            normalized.includes("consultation")
        ) {
            return "General Consultation";
        }

        return "";
    }

    function normalizeDateParts(year, month, day) {
        const normalizedMonth = String(month).padStart(2, "0");
        const normalizedDay = String(day).padStart(2, "0");
        return year + "-" + normalizedMonth + "-" + normalizedDay;
    }

    function formatDateForDisplay(isoDate) {
        const match = String(isoDate || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (!match) {
            return isoDate;
        }
        const monthNames = [
            "Jan",
            "Feb",
            "Mar",
            "Apr",
            "May",
            "Jun",
            "Jul",
            "Aug",
            "Sep",
            "Oct",
            "Nov",
            "Dec",
        ];
        const year = match[1];
        const monthIndex = Number(match[2]) - 1;
        const day = match[3];
        const monthLabel = monthNames[monthIndex] || match[2];
        return monthLabel + "-" + day + "-" + year;
    }

    function formatDateObject(dateObject) {
        return normalizeDateParts(
            dateObject.getFullYear(),
            dateObject.getMonth() + 1,
            dateObject.getDate()
        );
    }

    function addDays(baseDate, daysToAdd) {
        const nextDate = new Date(baseDate);
        nextDate.setDate(nextDate.getDate() + daysToAdd);
        return nextDate;
    }

    function getNextWeekday(baseDate, targetWeekday) {
        const currentWeekday = baseDate.getDay();
        let daysAhead = (targetWeekday - currentWeekday + 7) % 7;
        if (daysAhead === 0) {
            daysAhead = 7;
        }
        return addDays(baseDate, daysAhead);
    }

    function parseRelativeDateFromText(text) {
        const normalized = text.toLowerCase();
        const today = new Date();
        const weekdayMap = {
            sunday: 0,
            monday: 1,
            tuesday: 2,
            wednesday: 3,
            thursday: 4,
            friday: 5,
            saturday: 6,
        };

        if (normalized.includes("day after tomorrow")) {
            return formatDateObject(addDays(today, 2));
        }
        if (normalized.includes("today")) {
            return formatDateObject(today);
        }
        if (normalized.includes("tomorrow")) {
            return formatDateObject(addDays(today, 1));
        }

        const nextWeekdayMatch = normalized.match(
            /\bnext\s+(sunday|monday|tuesday|wednesday|thursday|friday|saturday)\b/
        );
        if (nextWeekdayMatch) {
            return formatDateObject(getNextWeekday(today, weekdayMap[nextWeekdayMatch[1]]));
        }

        const weekdayMatch = normalized.match(
            /\b(on\s+)?(sunday|monday|tuesday|wednesday|thursday|friday|saturday)\b/
        );
        if (weekdayMatch) {
            return formatDateObject(getNextWeekday(today, weekdayMap[weekdayMatch[2]]));
        }

        return "";
    }

    function parseDateFromText(text) {
        const isoMatch = text.match(/\b(\d{4})-(\d{2})-(\d{2})\b/);
        if (isoMatch) {
            return normalizeDateParts(isoMatch[1], isoMatch[2], isoMatch[3]);
        }

        const numericMatch = text.match(/\b(\d{1,2})\/(\d{1,2})\/(\d{4})\b/);
        if (numericMatch) {
            return normalizeDateParts(numericMatch[3], numericMatch[1], numericMatch[2]);
        }

        const monthNameMatch = text.match(
            /\b(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,)?\s+(\d{4})\b/i
        );
        if (monthNameMatch) {
            const month = monthMap[monthNameMatch[1].toLowerCase()];
            return normalizeDateParts(monthNameMatch[3], month, monthNameMatch[2]);
        }

        const reverseMonthNameMatch = text.match(
            /\b(\d{1,2})(?:st|nd|rd|th)?\s+of\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})\b/i
        );
        if (reverseMonthNameMatch) {
            const month = monthMap[reverseMonthNameMatch[2].toLowerCase()];
            return normalizeDateParts(reverseMonthNameMatch[3], month, reverseMonthNameMatch[1]);
        }

        return parseRelativeDateFromText(text);
    }

    function parseTimeFromText(text) {
        const labeledTime = extractFieldValue(text, ["time", "appointment time"]);
        const source = labeledTime || text;
        const timeMatch = source.match(/\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b/i);

        if (!timeMatch) {
            return "";
        }

        const hour = Number(timeMatch[1]);
        const minutes = timeMatch[2] || "00";
        const period = timeMatch[3].toUpperCase();

        if (hour < 1 || hour > 12) {
            return "";
        }

        return String(hour).padStart(2, "0") + ":" + minutes + " " + period;
    }

    function parseTimeWindowFromText(text) {
        const normalized = text.toLowerCase();

        if (normalized.includes("early morning")) {
            return "08:00 AM";
        }
        if (normalized.includes("morning")) {
            return "08:00 AM";
        }
        if (normalized.includes("noon")) {
            return "01:00 PM";
        }
        if (normalized.includes("afternoon")) {
            return "01:00 PM";
        }
        if (normalized.includes("evening")) {
            return "03:00 PM";
        }

        return "";
    }

    function extractFieldValue(text, labels) {
        for (let index = 0; index < labels.length; index += 1) {
            const label = labels[index];
            const pattern = new RegExp(label + "\\s*[:\\-]\\s*([^\\n]+)", "i");
            const match = text.match(pattern);
            if (match) {
                return match[1].trim();
            }
        }
        return "";
    }

    function extractBookingDetails(text) {
        const labeledType = extractFieldValue(text, ["type", "appointment type", "service", "consultation"]);
        const detectedType = detectAppointmentTypeFromText(text);

        return {
            appointment_type: normalizeAppointmentType(labeledType || detectedType),
            appointment_date: parseDateFromText(
                extractFieldValue(text, ["date", "appointment date"]) || text
            ),
            appointment_time: parseTimeFromText(text) || parseTimeWindowFromText(text),
            notes: extractFieldValue(text, ["notes", "reason", "concern"]),
        };
    }

    function validateBookingDetails(details) {
        const missing = [];

        if (!appointmentTypes.includes(details.appointment_type)) {
            missing.push("Consultation");
        }
        if (!details.appointment_date) {
            missing.push("Date");
        }
        if (!details.appointment_time) {
            missing.push("Time");
        }

        return missing;
    }

    function formatMissingFields(missing) {
        if (missing.length === 1) {
            return missing[0];
        }

        if (missing.length === 2) {
            return missing[0] + " and " + missing[1];
        }

        return missing.slice(0, -1).join(", ") + ", and " + missing[missing.length - 1];
    }

    async function startBookingFlow(message) {
        resetBookingFlow();
        chatbotState.awaitingBookingDetails = true;

        const initialDetails = extractBookingDetails(message || "");

        if (initialDetails.appointment_date) {
            chatbotState.pendingBookingDate = initialDetails.appointment_date;
        }
        if (initialDetails.appointment_time) {
            chatbotState.pendingBookingTime = initialDetails.appointment_time;
        }
        if (appointmentTypes.includes(initialDetails.appointment_type)) {
            chatbotState.pendingBookingType = initialDetails.appointment_type;
        }
        if (initialDetails.notes) {
            chatbotState.pendingBookingNotes = initialDetails.notes;
        }

        const missing = validateBookingDetails({
            appointment_type: chatbotState.pendingBookingType,
            appointment_date: chatbotState.pendingBookingDate,
            appointment_time: chatbotState.pendingBookingTime,
            notes: chatbotState.pendingBookingNotes,
        });

        addChatMessage(
            "bot",
            "Perfect, I can handle this for you using your saved account details."
        );

        if (!missing.length) {
            await submitChatbotBooking({
                appointment_type: chatbotState.pendingBookingType,
                appointment_date: chatbotState.pendingBookingDate,
                appointment_time: chatbotState.pendingBookingTime,
                notes: chatbotState.pendingBookingNotes || "",
            });
            return;
        }

        const capturedDetails = [
            chatbotState.pendingBookingType ? "the consultation" : "",
            chatbotState.pendingBookingDate ? "the date" : "",
            chatbotState.pendingBookingTime ? "the time" : "",
        ].filter(Boolean);

        if (capturedDetails.length) {
            addChatMessage(
                "bot",
                "I already got " + capturedDetails.join(", ") + "."
            );
        }
        addChatMessage(
            "bot",
            "Please send only the missing details: " + formatMissingFields(missing) + "."
        );
        addChatMessage(
            "bot",
            "Format: Consultation: General Consultation\nDate: 2026-04-18\nTime: 10:00 AM\nNotes: Fever and cough"
        );
    }

    async function showAvailability(selectedDate) {
        try {
            const endpoint = selectedDate
                ? "/api/availability?date=" + encodeURIComponent(selectedDate)
                : "/api/availability";
            const response = await fetch(endpoint);
            const data = await response.json();

            if (selectedDate) {
                if (data.slots && data.slots.length) {
                    addChatMessage(
                        "bot",
                        "Here are the available times for " +
                            formatDateForDisplay(selectedDate) +
                            ": " +
                            data.slots.join(", ")
                    );
                } else {
                    addChatMessage(
                        "bot",
                        "I checked for " +
                            formatDateForDisplay(selectedDate) +
                            " and all slots are already taken. I can help you find the next available date."
                    );
                }
                return;
            }

            if (!data.upcoming || !data.upcoming.length) {
                addChatMessage("bot", "I couldn't find any open schedules right now, but you can try again in a moment and I’ll check again.");
                return;
            }

            const lines = data.upcoming.map(function (entry) {
                return entry.label + ": " + entry.slots.join(", ");
            });
            addChatMessage("bot", "Sure, here are the next available schedules:\n" + lines.join("\n"));
        } catch (error) {
            addChatMessage(
                "bot",
                "I couldn't load the available schedules right now. Please try again in a moment."
            );
        }
    }

    async function submitChatbotBooking(details) {
        try {
            const availabilityResponse = await fetch(
                "/api/availability?date=" + encodeURIComponent(details.appointment_date)
            );
            const availabilityData = await availabilityResponse.json();
            chatbotState.availableSlotsForSelectedDate = (availabilityData.slots || []).map(function (slot) {
                return slot.toUpperCase();
            });

            if (!chatbotState.availableSlotsForSelectedDate.length) {
                addChatMessage(
                    "bot",
                    "That date is fully booked right now. Share another date and I’ll check it for you."
                );
                return;
            }

            if (!chatbotState.availableSlotsForSelectedDate.includes(details.appointment_time)) {
                addChatMessage(
                    "bot",
                    "The available schedule for " +
                        formatDateForDisplay(details.appointment_date) +
                        " is: " +
                        chatbotState.availableSlotsForSelectedDate.join(", ")
                );
                addChatMessage(
                    "bot",
                    "Pick one of those times and send it to me. No need to resend all your details."
                );
                return;
            }

            const response = await fetch("/api/chatbot/book", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(details),
            });
            const data = await response.json();

            if (!response.ok) {
                addChatMessage("bot", data.message || "I couldn't complete the booking.");
                if (data.available_slots && data.available_slots.length) {
                    addChatMessage(
                        "bot",
                        "Available schedule for " +
                            details.appointment_date +
                            ": " +
                            data.available_slots.join(", ")
                    );
                }
                return;
            }

            addChatMessage(
                "bot",
                "Booked successfully for " +
                    (chatbotProfile.name || data.booking.patient) +
                    " on " + formatDateForDisplay(data.booking.date) +
                    " at " +
                    data.booking.time +
                    "."
            );
            addChatMessage(
                "bot",
                "Appointment type: " + data.booking.type + "."
            );
            resetBookingFlow();
        } catch (error) {
            addChatMessage(
                "bot",
                "I couldn't save the booking right now. Please try again in a moment."
            );
        }
    }

    async function handleBookingDetailsMessage(message) {
        const details = extractBookingDetails(message);

        if (chatbotState.pendingBookingDate && !details.appointment_date) {
            details.appointment_date = chatbotState.pendingBookingDate;
        }
        if (chatbotState.pendingBookingTime && !details.appointment_time) {
            details.appointment_time = chatbotState.pendingBookingTime;
        }
        if (chatbotState.pendingBookingType && !details.appointment_type) {
            details.appointment_type = chatbotState.pendingBookingType;
        }
        if (chatbotState.pendingBookingNotes && !details.notes) {
            details.notes = chatbotState.pendingBookingNotes;
        }

        if (!details.notes && message.trim().toLowerCase() !== "none") {
            details.notes = "";
        }

        if (message.trim().toLowerCase() === "none") {
            details.notes = "";
        }

        const missing = validateBookingDetails(details);
        if (missing.length) {
            chatbotState.pendingBookingDate = details.appointment_date || chatbotState.pendingBookingDate;
            chatbotState.pendingBookingTime = details.appointment_time || chatbotState.pendingBookingTime;
            chatbotState.pendingBookingType = details.appointment_type || chatbotState.pendingBookingType;
            chatbotState.pendingBookingNotes = details.notes || chatbotState.pendingBookingNotes;

            addChatMessage(
                "bot",
                "I still need: " + formatMissingFields(missing) + "."
            );
            addChatMessage(
                "bot",
                "You don't need to resend the details I already understood."
            );
            return;
        }

        await submitChatbotBooking(details);
    }

    async function askAiChatbot(message) {
        try {
            const response = await fetch("/api/chatbot/respond", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    message: message,
                    user_name: chatbotState.rememberedName || chatbotProfile.name || "",
                    preferred_tone: chatbotState.preferredTone || "warm",
                }),
            });
            const data = await response.json();
            if (!response.ok) {
                return "";
            }
            return (data.reply || "").trim();
        } catch (error) {
            return "";
        }
    }

    async function respondToGeneralMessage(message) {
        const normalized = message.toLowerCase();
        const requestedDate = parseDateFromText(message);
        const isDoctorQuestion =
            normalized.includes("doctor") ||
            normalized.includes("physician") ||
            normalized.includes("dentist") ||
            normalized.includes("pediatrician") ||
            normalized.includes("who is available");
        const isAvailabilityQuestion =
            normalized.includes("schedule") ||
            normalized.includes("slot") ||
            normalized.includes("available schedule") ||
            normalized.includes("available slot") ||
            normalized.includes("what time") ||
            normalized.includes("what times");
        const isBookingIntent =
            normalized.includes("book") ||
            normalized.includes("booking") ||
            normalized.includes("schedule me") ||
            normalized.includes("make an appointment");

        if (isBookingIntent) {
            await startBookingFlow(message);
            return;
        }

        if (isDoctorQuestion) {
            const aiDoctorReply = await askAiChatbot(message);
            if (aiDoctorReply) {
                addChatMessage("bot", aiDoctorReply);
                return;
            }
        }

        if (requestedDate && isAvailabilityQuestion) {
            await showAvailability(requestedDate);
            return;
        }

        if (requestedDate) {
            await showAvailability(requestedDate);
            return;
        }

        if (isAvailabilityQuestion) {
            await showAvailability();
            return;
        }

        const aiReply = await askAiChatbot(message);
        if (aiReply) {
            addChatMessage("bot", aiReply);
            return;
        }

            addChatMessage(
                "bot",
                "I can help with almost anything, and I’m best at scheduling. If you want, ask me to check a date or book an appointment for you."
            );
    }

    async function handleChatSubmission(message) {
        if (!isLoggedIn) {
            addLoginRequiredPrompt();
            showLogin();
            return;
        }

        rememberUserDetails(message);
        addChatMessage("user", message);

        if (chatbotState.awaitingBookingDetails) {
            await handleBookingDetailsMessage(message);
            return;
        }

        await respondToGeneralMessage(message);
    }

    if (chatbotToggle) {
        chatbotToggle.addEventListener("click", function () {
            if (chatbotPanel.classList.contains("is-open")) {
                closeChatbotPanel();
                return;
            }
            openChatbot();
        });
    }

    if (tryChatbotBtn) {
        tryChatbotBtn.addEventListener("click", function () {
            openChatbot();
        });
    }

    if (contactForm) {
        contactForm.addEventListener("submit", function (event) {
            if (!isLoggedIn) {
                event.preventDefault();
                showLogin();
            }
        });
    }

    openChatbotLinks.forEach(function (link) {
        link.addEventListener("click", function (event) {
            event.preventDefault();
            openChatbot();
        });
    });

    if (chatbotClose) {
        chatbotClose.addEventListener("click", function () {
            closeChatbotPanel();
        });
    }

    quickActionButtons.forEach(function (button) {
        button.addEventListener("click", async function () {
            openChatbot();
            const quickMessage = button.dataset.message || "";
            await handleChatSubmission(quickMessage);
        });
    });

    if (chatbotForm) {
        chatbotForm.addEventListener("submit", async function (event) {
            event.preventDefault();
            const message = chatbotInput.value.trim();
            if (!message) {
                return;
            }

            chatbotInput.value = "";
            await handleChatSubmission(message);
            chatbotInput.focus();
        });
    }
});

