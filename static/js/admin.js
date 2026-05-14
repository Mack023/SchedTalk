document.addEventListener("DOMContentLoaded", () => {
    const menuToggle = document.getElementById("menuToggle");
    const sidebar = document.getElementById("adminSidebar");

    if (menuToggle && sidebar) {
        menuToggle.addEventListener("click", () => {
            sidebar.classList.toggle("open");
        });

        document.addEventListener("click", (event) => {
            const clickedInsideSidebar = sidebar.contains(event.target);
            const clickedToggle = menuToggle.contains(event.target);

            if (!clickedInsideSidebar && !clickedToggle && window.innerWidth <= 860) {
                sidebar.classList.remove("open");
            }
        });
    }

    const openButtons = document.querySelectorAll("[data-open-modal]");
    const closeButtons = document.querySelectorAll("[data-close-modal]");

    openButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const modal = document.getElementById(button.dataset.openModal);
            if (modal) {
                modal.classList.add("is-open");
            }
        });
    });

    closeButtons.forEach((button) => {
        button.addEventListener("click", () => {
            const modal = document.getElementById(button.dataset.closeModal);
            if (modal) {
                modal.classList.remove("is-open");
            }
        });
    });

    document.querySelectorAll(".modal").forEach((modal) => {
        modal.addEventListener("click", (event) => {
            if (event.target === modal) {
                modal.classList.remove("is-open");
            }
        });
    });

    const patientSearch = document.getElementById("patientSearch");
    const patientTable = document.getElementById("patientTable");

    if (patientSearch && patientTable) {
        const rowsPerPage = 10;
        const patientRows = Array.from(patientTable.querySelectorAll("tbody tr[data-patient-row], tbody tr:not(.empty-row)"));
        const pagination = document.getElementById("patientPagination");
        const prevButton = document.getElementById("patientPrevPage");
        const nextButton = document.getElementById("patientNextPage");
        const pageLabel = document.getElementById("patientPageLabel");
        let currentPage = 1;
        let filteredRows = patientRows;

        function renderPatientPage(direction = "next") {
            const totalPages = Math.max(Math.ceil(filteredRows.length / rowsPerPage), 1);
            currentPage = Math.min(Math.max(currentPage, 1), totalPages);
            const startIndex = (currentPage - 1) * rowsPerPage;
            const visibleRows = new Set(filteredRows.slice(startIndex, startIndex + rowsPerPage));

            patientTable.classList.remove("slide-next", "slide-prev");
            void patientTable.offsetWidth;
            patientTable.classList.add(direction === "prev" ? "slide-prev" : "slide-next");

            patientRows.forEach((row) => {
                row.style.display = visibleRows.has(row) ? "" : "none";
            });

            if (pagination) {
                pagination.hidden = filteredRows.length <= rowsPerPage;
            }
            if (prevButton) {
                prevButton.disabled = currentPage <= 1;
            }
            if (nextButton) {
                nextButton.disabled = currentPage >= totalPages;
            }
            if (pageLabel) {
                pageLabel.textContent = `Page ${currentPage} of ${totalPages}`;
            }
        }

        patientSearch.addEventListener("input", () => {
            const query = patientSearch.value.trim().toLowerCase();
            filteredRows = patientRows.filter((row) => row.textContent.toLowerCase().includes(query));
            currentPage = 1;
            renderPatientPage("next");
        });

        if (prevButton) {
            prevButton.addEventListener("click", () => {
                currentPage -= 1;
                renderPatientPage("prev");
            });
        }

        if (nextButton) {
            nextButton.addEventListener("click", () => {
                currentPage += 1;
                renderPatientPage("next");
            });
        }

        renderPatientPage("next");
    }

    const dashboardStats = document.querySelector("[data-dashboard-summary-url]");
    const weeklyBookingsChart = document.getElementById("weeklyBookingsChart");
    const weeklyBookingsTotal = document.getElementById("weeklyBookingsTotal");

    function escapeHtml(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/\"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function renderWeeklyBookings(weeklyBookings, lastWeekBookings = []) {
        if (!weeklyBookingsChart || !Array.isArray(weeklyBookings)) {
            return;
        }

        const safeWeek = Array.isArray(weeklyBookings) ? weeklyBookings : [];
        const safeLastWeek = Array.isArray(lastWeekBookings) ? lastWeekBookings : [];
        const maxCount = Math.max(
            ...safeWeek.map((item) => Number(item.count) || 0),
            ...safeLastWeek.map((item) => Number(item.count) || 0),
            1,
            5
        );
        const totalBookings = safeWeek.reduce((sum, item) => sum + (Number(item.count) || 0), 0);
        const ySteps = 5;
        const yMax = Math.ceil(maxCount / ySteps) * ySteps;

        if (weeklyBookingsTotal) {
            weeklyBookingsTotal.textContent = `${totalBookings} total bookings`;
        }

        const minChartWidth = 760;
        const widthPerPoint = 52;
        const width = Math.max(minChartWidth, safeWeek.length * widthPerPoint);
        const height = 260;
        const paddingLeft = 56;
        const paddingRight = 24;
        const paddingTop = 18;
        const paddingBottom = 48;
        const chartWidth = width - paddingLeft - paddingRight;
        const chartHeight = height - paddingTop - paddingBottom;
        const xStep = safeWeek.length > 1 ? chartWidth / (safeWeek.length - 1) : chartWidth;

        const points = safeWeek.map((item, index) => {
            const count = Number(item.count) || 0;
            const x = paddingLeft + (xStep * index);
            const y = paddingTop + chartHeight - ((count / yMax) * chartHeight);
            const date = (item.date || "").slice(5).replace("-", "/");
            return {
                x,
                y,
                count,
                day: item.day || "",
                date,
            };
        });
        const lastWeekPoints = safeWeek.map((item, index) => {
            const fallback = safeLastWeek[index] || {};
            const count = Number(fallback.count) || 0;
            const x = paddingLeft + (xStep * index);
            const y = paddingTop + chartHeight - ((count / yMax) * chartHeight);
            return {
                x,
                y,
                count,
            };
        });
        const linePath = buildSmoothPath(points);
        const lastWeekPathData = buildSmoothPath(lastWeekPoints);
        const axisY = paddingTop + chartHeight;
        const thisWeekAreaPath = buildAreaPath(points, axisY);
        const lastWeekAreaPath = buildAreaPath(lastWeekPoints, axisY);

        function toSignDelta(delta) {
            if (delta > 0) return `+${delta}`;
            return `${delta}`;
        }

        function buildSmoothPath(pathPoints) {
            if (!pathPoints.length) {
                return "";
            }
            if (pathPoints.length === 1) {
                return `M ${pathPoints[0].x} ${pathPoints[0].y}`;
            }

            let d = `M ${pathPoints[0].x} ${pathPoints[0].y}`;
            for (let i = 0; i < pathPoints.length - 1; i += 1) {
                const p0 = pathPoints[i - 1] || pathPoints[i];
                const p1 = pathPoints[i];
                const p2 = pathPoints[i + 1];
                const p3 = pathPoints[i + 2] || p2;

                const cp1x = p1.x + (p2.x - p0.x) / 6;
                const cp1y = p1.y + (p2.y - p0.y) / 6;
                const cp2x = p2.x - (p3.x - p1.x) / 6;
                const cp2y = p2.y - (p3.y - p1.y) / 6;
                d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${p2.x} ${p2.y}`;
            }
            return d;
        }

        function buildAreaPath(pathPoints, baselineY) {
            if (!pathPoints.length) {
                return "";
            }
            const smooth = buildSmoothPath(pathPoints);
            const first = pathPoints[0];
            const last = pathPoints[pathPoints.length - 1];
            return `${smooth} L ${last.x} ${baselineY} L ${first.x} ${baselineY} Z`;
        }

        const yGridLines = Array.from({ length: ySteps + 1 }, (_, i) => {
            const value = yMax - ((yMax / ySteps) * i);
            const y = paddingTop + ((chartHeight / ySteps) * i);
            return `
                <line x1="${paddingLeft}" y1="${y}" x2="${width - paddingRight}" y2="${y}"></line>
                <text class="chart-y-label" x="${paddingLeft - 10}" y="${y + 4}" text-anchor="end">${value}</text>
            `;
        }).join("");

        const labelStep = safeWeek.length > 14 ? Math.ceil(safeWeek.length / 10) : 1;

        weeklyBookingsChart.innerHTML = `
            <svg class="weekly-chart-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-label="Patient bookings line chart">
                <g class="chart-grid">
                    ${yGridLines}
                    ${points.map((point) => `<line x1="${point.x}" y1="${paddingTop}" x2="${point.x}" y2="${axisY}"></line>`).join("")}
                </g>
                <line class="chart-axis" x1="${paddingLeft}" y1="${axisY}" x2="${width - paddingRight + 6}" y2="${axisY}"></line>
                <line class="chart-axis" x1="${paddingLeft}" y1="${paddingTop - 4}" x2="${paddingLeft}" y2="${axisY}"></line>
                <path class="chart-area-last-week" d="${lastWeekAreaPath}"></path>
                <path class="chart-area-this-week" d="${thisWeekAreaPath}"></path>
                <path class="chart-line chart-line-last-week" d="${lastWeekPathData}"></path>
                <path class="chart-line" d="${linePath}"></path>
                ${lastWeekPoints.map((point, index) => `
                    <circle class="chart-point chart-point-last-week" cx="${point.x}" cy="${point.y}" r="4.2" style="animation-delay:${(index * 0.1 + 0.32).toFixed(2)}s"></circle>
                `).join("")}
                ${points.map((point, index) => `
                    <circle class="chart-point chart-point-this-week" cx="${point.x}" cy="${point.y}" r="6.1" data-day="${escapeHtml(point.day)}" data-date="${escapeHtml(point.date)}" data-this-week="${point.count}" data-last-week="${lastWeekPoints[index] ? lastWeekPoints[index].count : 0}" style="animation-delay:${(index * 0.12 + 0.45).toFixed(2)}s"></circle>
                    <text class="chart-delta-label ${((point.count - (lastWeekPoints[index] ? lastWeekPoints[index].count : 0)) > 0) ? "chart-delta-up" : ((point.count - (lastWeekPoints[index] ? lastWeekPoints[index].count : 0)) < 0) ? "chart-delta-down" : "chart-delta-equal"}" x="${point.x}" y="${point.y - 27}" text-anchor="middle">${toSignDelta(point.count - (lastWeekPoints[index] ? lastWeekPoints[index].count : 0))}</text>
                    ${(index % labelStep === 0 || index === safeWeek.length - 1) ? `<text class="chart-label" x="${point.x}" y="${height - 14}" text-anchor="middle">${escapeHtml(point.day)} ${escapeHtml(point.date)}</text>` : ""}
                `).join("")}
            </svg>
        `;

        weeklyBookingsChart.querySelectorAll(".chart-line").forEach((line) => {
            if (typeof line.getTotalLength === "function") {
                const length = line.getTotalLength();
                line.style.setProperty("--line-len", `${length}`);
            }
        });

        let tooltip = weeklyBookingsChart.querySelector(".chart-tooltip");
        if (!tooltip) {
            tooltip = document.createElement("div");
            tooltip.className = "chart-tooltip";
            weeklyBookingsChart.appendChild(tooltip);
        }

        const chartRect = weeklyBookingsChart.getBoundingClientRect();
        weeklyBookingsChart.querySelectorAll(".chart-point-this-week").forEach((point) => {
            point.addEventListener("mouseenter", () => {
                const thisWeek = Number(point.dataset.thisWeek || "0");
                const lastWeek = Number(point.dataset.lastWeek || "0");
                const delta = thisWeek - lastWeek;
                const deltaText = delta > 0 ? `+${delta}` : `${delta}`;
                tooltip.innerHTML = `${escapeHtml(point.dataset.day || "")} ${escapeHtml(point.dataset.date || "")}<br>This week: <strong>${thisWeek}</strong><br>Last week: <strong>${lastWeek}</strong><br>Delta: <strong>${deltaText}</strong>`;
                tooltip.classList.add("is-visible");
            });
            point.addEventListener("mousemove", (event) => {
                const x = event.clientX - chartRect.left + 10;
                const y = event.clientY - chartRect.top - 42;
                tooltip.style.left = `${x}px`;
                tooltip.style.top = `${y}px`;
            });
            point.addEventListener("mouseleave", () => {
                tooltip.classList.remove("is-visible");
            });
        });
    }

    if (dashboardStats) {
        const summaryUrl = dashboardStats.dataset.dashboardSummaryUrl;
        const todayAppointmentsCount = document.getElementById("todayAppointmentsCount");
        const todayAppointmentsLabel = document.getElementById("todayAppointmentsLabel");
        const pendingAppointmentsCount = document.getElementById("pendingAppointmentsCount");
        const completedAppointmentsCount = document.getElementById("completedAppointmentsCount");
        const cancelledAppointmentsCount = document.getElementById("cancelledAppointmentsCount");
        const todayScheduleList = document.getElementById("todayScheduleList");
        const todayScheduleEmpty = document.getElementById("todayScheduleEmpty");

        function renderTodaySchedule(appointments) {
            if (!todayScheduleList && !todayScheduleEmpty) {
                return;
            }

            if (appointments.length === 0) {
                if (todayScheduleList) {
                    todayScheduleList.innerHTML = "";
                    todayScheduleList.style.display = "none";
                }

                if (todayScheduleEmpty) {
                    todayScheduleEmpty.style.display = "";
                }
                return;
            }

            if (todayScheduleList) {
                todayScheduleList.innerHTML = appointments.map((appointment) => `
                    <div class="list-item">
                        <div>
                            <strong>${escapeHtml(appointment.patient)}</strong>
                            <p>${escapeHtml(appointment.type)} with ${escapeHtml(appointment.doctor)}</p>
                        </div>
                        <div class="item-meta">
                            <span>${escapeHtml(appointment.time)}</span>
                            <span class="status-pill ${escapeHtml(appointment.status_class)}">${escapeHtml(appointment.status)}</span>
                        </div>
                    </div>
                `).join("");
                todayScheduleList.style.display = "";
            }

            if (todayScheduleEmpty) {
                todayScheduleEmpty.style.display = "none";
            }
        }

        async function refreshDashboardSummary() {
            try {
                const response = await fetch(summaryUrl, {
                    headers: {
                        "X-Requested-With": "XMLHttpRequest",
                    },
                });

                if (!response.ok) {
                    return;
                }

                const payload = await response.json();
                if (!payload.success || !payload.summary) {
                    return;
                }

                const { summary } = payload;

                if (todayAppointmentsCount) {
                    todayAppointmentsCount.textContent = summary.stats.today;
                }
                if (todayAppointmentsLabel) {
                    todayAppointmentsLabel.textContent = summary.today_label;
                }
                if (pendingAppointmentsCount) {
                    pendingAppointmentsCount.textContent = summary.stats.pending;
                }
                if (completedAppointmentsCount) {
                    completedAppointmentsCount.textContent = summary.stats.completed;
                }
                if (cancelledAppointmentsCount) {
                    cancelledAppointmentsCount.textContent = summary.stats.cancelled;
                }

                renderTodaySchedule(summary.today_appointments || []);
                renderWeeklyBookings(
                    summary.weekly_bookings || [],
                    summary.last_week_bookings || []
                );
            } catch (error) {
                // Keep the current dashboard values if refresh fails.
            }
        }

        if (weeklyBookingsChart) {
            try {
                renderWeeklyBookings(
                    JSON.parse(weeklyBookingsChart.dataset.weeklyBookings || "[]"),
                    JSON.parse(weeklyBookingsChart.dataset.lastWeekBookings || "[]")
                );
            } catch (error) {
                renderWeeklyBookings([], []);
            }
        }
        refreshDashboardSummary();
        window.setInterval(refreshDashboardSummary, 5000);
    }

    if (!dashboardStats && weeklyBookingsChart) {
        const graphsDataUrl = weeklyBookingsChart.dataset.graphsDataUrl;
        const daysFilter = document.getElementById("graphsDaysFilter");
        const doctorFilter = document.getElementById("graphsDoctorFilter");
        const kpiTotalBookings = document.getElementById("kpiTotalBookings");
        const kpiCompletionRate = document.getElementById("kpiCompletionRate");
        const kpiCancellationRate = document.getElementById("kpiCancellationRate");
        const kpiNoShowRate = document.getElementById("kpiNoShowRate");
        const graphsInsights = document.getElementById("graphsInsights");

        function renderGraphsKpis(kpis) {
            if (!kpis) {
                return;
            }
            if (kpiTotalBookings) {
                kpiTotalBookings.textContent = kpis.total_bookings ?? 0;
            }
            if (kpiCompletionRate) {
                kpiCompletionRate.textContent = `${kpis.completion_rate ?? 0}%`;
            }
            if (kpiCancellationRate) {
                kpiCancellationRate.textContent = `${kpis.cancellation_rate ?? 0}%`;
            }
            if (kpiNoShowRate) {
                kpiNoShowRate.textContent = `${kpis.no_show_rate ?? 0}%`;
            }
        }

        function renderGraphsInsights(insights) {
            if (!graphsInsights || !Array.isArray(insights)) {
                return;
            }
            graphsInsights.innerHTML = insights
                .map((insight) => `<article class="insight-card">${escapeHtml(insight)}</article>`)
                .join("");
        }

        try {
            renderWeeklyBookings(
                JSON.parse(weeklyBookingsChart.dataset.weeklyBookings || "[]"),
                JSON.parse(weeklyBookingsChart.dataset.lastWeekBookings || "[]")
            );
        } catch (error) {
            renderWeeklyBookings([], []);
        }

        if (graphsDataUrl) {
            const refreshGraphs = async () => {
                try {
                    const days = daysFilter ? daysFilter.value : "7";
                    const doctor = doctorFilter ? doctorFilter.value : "all";
                    const query = new URLSearchParams({ days, doctor }).toString();
                    const response = await fetch(`${graphsDataUrl}?${query}`, {
                        headers: {
                            "X-Requested-With": "XMLHttpRequest",
                        },
                    });
                    if (!response.ok) {
                        return;
                    }
                    const payload = await response.json();
                    if (!payload.success || !payload.data) {
                        return;
                    }
                    const graphData = payload.data;
                    renderWeeklyBookings(
                        graphData.weekly_bookings || [],
                        graphData.last_week_bookings || []
                    );
                    renderGraphsKpis(graphData.kpis);
                    renderGraphsInsights(graphData.insights);
                } catch (error) {
                    // Keep existing graph if refresh fails.
                }
            };

            if (daysFilter) {
                daysFilter.addEventListener("change", refreshGraphs);
            }
            if (doctorFilter) {
                doctorFilter.addEventListener("change", refreshGraphs);
            }
            refreshGraphs();
        }
    }
});
