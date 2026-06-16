const API_BASE = '/api';

const state = {
    studies: [],
    workers: [],
    queues: [],
    tasks: [],
    stats: {}
};

async function fetchJSON(url) {
    const response = await fetch(url);
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
}

async function loadStats() {
    try {
        const [statsData, queuesData] = await Promise.all([
            fetchJSON(`${API_BASE}/stats`),
            fetchJSON(`${API_BASE}/queues`)
        ]);

        state.stats = statsData;

        // Calculate total backlog in cluster
        const totalBacklog = (queuesData.queues || []).reduce((acc, q) => acc + (q.items || 0), 0);

        document.getElementById('totalStudies').textContent = statsData.studies?.total ?? '-';
        document.getElementById('totalTrials').textContent = statsData.trials?.total ?? '-';
        document.getElementById('completedTrials').textContent = statsData.trials?.completed ?? '-';
        document.getElementById('runningTrials').textContent = statsData.trials?.running ?? '-';
        document.getElementById('failedTrials').textContent = statsData.trials?.failed ?? '-';

        // Replace Worker Count with Cluster Backlog for the Manager View
        const workerElement = document.getElementById('workerCount');
        workerElement.textContent = totalBacklog;
        workerElement.parentElement.querySelector('.stat-label').textContent = 'Cluster Backlog (Tasks)';
        if (totalBacklog > 0) {
            workerElement.parentElement.classList.add('stat-danger');
        } else {
            workerElement.parentElement.classList.remove('stat-danger');
        }

        const now = new Date();
        document.getElementById('lastUpdate').textContent = `Cluster Update: ${now.toLocaleTimeString()}`;
    } catch (e) {
        console.error('Error loading stats:', e);
    }
}

async function loadStudies() {
    try {
        const data = await fetchJSON(`${API_BASE}/studies`);
        state.studies = data.studies || [];

        const container = document.getElementById('studiesList');

        if (state.studies.length === 0) {
            container.innerHTML = '<div class="empty-state">No hay estudios disponibles</div>';
            return;
        }

        container.innerHTML = state.studies.map(study => `
            <div class="study-card" onclick="showStudyDetails('${study.study_name}')">
                <div class="study-header">
                    <div class="study-name">${study.study_name}</div>
                    <div class="study-direction ${study.direction}">${study.direction}</div>
                </div>
                <div class="study-stats">
                    <div class="study-stat">
                        <span class="study-stat-label">Trials</span>
                        <span class="study-stat-value">${study.n_trials ?? 0}</span>
                    </div>
                    <div class="study-stat">
                        <span class="study-stat-label">Mejor Valor</span>
                        <span class="study-stat-value">${study.best_value?.toFixed(4) ?? '-'}</span>
                    </div>
                    <div class="study-stat">
                        <span class="study-stat-label">Inicio</span>
                        <span class="study-stat-value">${study.start_time ? new Date(study.start_time).toLocaleDateString() : '-'}</span>
                    </div>
                </div>
                ${study.best_params ? `
                    <div class="best-params">
                        <div class="best-params-title">Mejores Parámetros</div>
                        <div class="params-grid">
                            ${Object.entries(study.best_params).map(([key, value]) => `
                                <div class="param-item">
                                    <span class="param-name">${key}:</span>
                                    <span class="param-value">${typeof value === 'number' ? value.toFixed(4) : value}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>
        `).join('');
    } catch (e) {
        console.error('Error loading studies:', e);
        document.getElementById('studiesList').innerHTML =
            '<div class="empty-state">Error cargando estudios</div>';
    }
}

async function showStudyDetails(studyName) {
    try {
        const trials = await fetchJSON(`${API_BASE}/studies/${studyName}/trials`);

        const modal = document.getElementById('modal');
        const modalBody = document.getElementById('modalBody');

        modalBody.innerHTML = `
            <h2>Trials - ${studyName}</h2>
            <div class="trial-list">
                ${trials.trials.length === 0 ?
                    '<div class="empty-state">No hay trials</div>' :
                    trials.trials.map(trial => `
                        <div class="trial-item">
                            <div>
                                <div class="trial-id">Trial #${trial.trial_id}</div>
                                ${trial.params ? `
                                    <div class="params-grid" style="margin-top: 8px;">
                                        ${Object.entries(trial.params).slice(0, 5).map(([k, v]) => `
                                            <div class="param-item">
                                                <span class="param-name">${k}:</span>
                                                <span class="param-value">${typeof v === 'number' ? v.toFixed(4) : v}</span>
                                            </div>
                                        `).join('')}
                                    </div>
                                ` : ''}
                            </div>
                            <div style="text-align: right;">
                                <div class="trial-state ${trial.state}">${trial.state}</div>
                                ${trial.value !== null ? `<div class="trial-value">${trial.value.toFixed(4)}</div>` : ''}
                            </div>
                        </div>
                    `).join('')
                }
            </div>
        `;

        modal.classList.add('active');
    } catch (e) {
        console.error('Error loading study details:', e);
    }
}

async function loadWorkers() {
    try {
        const data = await fetchJSON(`${API_BASE}/workers`);
        state.workers = data.workers || [];

        const container = document.getElementById('workersList');

        if (state.workers.length === 0) {
            container.innerHTML = '<div class="empty-state">No hay workers online</div>';
            return;
        }

        container.innerHTML = state.workers.map(worker => `
            <div class="worker-card">
                <div class="worker-info">
                    <h3>${worker.name}</h3>
                    <div class="worker-status">
                        <span class="status-dot"></span>
                        ${worker.status}
                    </div>
                </div>
                <div class="worker-tasks">
                    <div class="worker-tasks-count">${worker.active_tasks?.length || 0}</div>
                    <div class="worker-tasks-label">tareas activas</div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Error loading workers:', e);
        document.getElementById('workersList').innerHTML =
            '<div class="empty-state">Error cargando workers</div>';
    }
}

async function loadQueues() {
    try {
        const data = await fetchJSON(`${API_BASE}/queues`);
        state.queues = data.queues || [];

        const container = document.getElementById('queuesList');

        if (state.queues.length === 0) {
            container.innerHTML = '<div class="empty-state">No hay información de colas disponible</div>';
            return;
        }

        container.innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; width: 100%;">
                ${state.queues.map(queue => `
                    <div class="queue-card ${queue.items > 0 ? 'active' : ''}" style="border-left: 4px solid ${queue.priority === 'high' ? '#ef4444' : '#3b82f6'};">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div class="queue-name" style="font-weight: 700;">${queue.name}</div>
                                <div style="font-size: 0.8rem; color: var(--text-dim);">${queue.priority.toUpperCase()} PRIORITY</div>
                            </div>
                            <div class="queue-items" style="font-size: 1.5rem; font-weight: 800; color: ${queue.items > 0 ? 'var(--primary)' : 'var(--text-dim)'};">
                                ${queue.items}
                            </div>
                        </div>
                        ${queue.items > 0 ? '<div style="margin-top: 10px; font-size: 0.75rem; color: #f59e0b;"><i class="fas fa-clock"></i> Tareas esperando procesamiento</div>' : ''}
                    </div>
                `).join('')}
            </div>
        `;
    } catch (e) {
        console.error('Error loading queues:', e);
        document.getElementById('queuesList').innerHTML = '<div class="empty-state">Error cargando colas</div>';
    }
}

async function loadTasks() {
    try {
        const data = await fetchJSON(`${API_BASE}/workers/active-tasks`);
        state.tasks = data.tasks || [];

        const container = document.getElementById('tasksList');

        if (state.tasks.length === 0) {
            container.innerHTML = '<div class="empty-state">No hay tareas en ejecución</div>';
            return;
        }

        container.innerHTML = state.tasks.map(task => `
            <div class="task-card">
                <div>
                    <div class="task-name">${task.name}</div>
                    <div class="task-id">${task.id}</div>
                </div>
                <div class="task-worker">${task.worker}</div>
            </div>
        `).join('');
    } catch (e) {
        console.error('Error loading tasks:', e);
        document.getElementById('tasksList').innerHTML =
            '<div class="empty-state">Error cargando tareas</div>';
    }
}

async function loadAll() {
    await Promise.all([
        loadStats(),
        loadStudies(),
        loadWorkers(),
        loadQueues(),
        loadTasks()
    ]);
}

document.addEventListener('DOMContentLoaded', () => {
    loadAll();

    document.getElementById('refreshBtn').addEventListener('click', loadAll);

    const tabs = document.querySelectorAll('.tab-btn');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

            tab.classList.add('active');
            document.getElementById(`${tab.dataset.tab}-tab`).classList.add('active');
        });
    });

    const modal = document.getElementById('modal');
    const closeBtn = document.querySelector('.modal-close');

    closeBtn.addEventListener('click', () => {
        modal.classList.remove('active');
    });

    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.classList.remove('active');
        }
    });

    setInterval(loadAll, 30000);
});
