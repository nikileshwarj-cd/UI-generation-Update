/**
 * ui/static/app.js
 * 100% Dynamic Frontend Controller for Project-Centric Development Platform.
 * Queries /api/v1/projects to render ONLY real existing projects on disk.
 */

document.addEventListener('DOMContentLoaded', () => {
    const projectsDashboardView = document.getElementById('projectsDashboardView');
    const existingProjectsGrid = document.getElementById('existingProjectsGrid');
    const projectCountBadge = document.getElementById('projectCountBadge');

    const headerCreateProjectBtn = document.getElementById('headerCreateProjectBtn');
    const backToProjectsBtn = document.getElementById('backToProjectsBtn');

    const createProjectModalOverlay = document.getElementById('createProjectModalOverlay');
    const closeCreateModalBtn = document.getElementById('closeCreateModalBtn');
    const cancelCreateBtn = document.getElementById('cancelCreateBtn');
    const createProjectForm = document.getElementById('createProjectForm');

    const projectWorkspaceView = document.getElementById('projectWorkspaceView');
    const activeProjectIdBadge = document.getElementById('activeProjectIdBadge');
    const activeProjectTitle = document.getElementById('activeProjectTitle');
    const activeTechStackChips = document.getElementById('activeTechStackChips');
    const addStoryForm = document.getElementById('addStoryForm');
    const newUserStory = document.getElementById('newUserStory');

    const tabStoryGraphBtn = document.getElementById('tabStoryGraphBtn');
    const tabCodeFilesBtn = document.getElementById('tabCodeFilesBtn');
    const tabLivePreviewBtn = document.getElementById('tabLivePreviewBtn');
    const tabTraceabilityBtn = document.getElementById('tabTraceabilityBtn');

    const tabStoryGraphContent = document.getElementById('tabStoryGraphContent');
    const tabCodeFilesContent = document.getElementById('tabCodeFilesContent');
    const tabLivePreviewContent = document.getElementById('tabLivePreviewContent');
    const tabTraceabilityContent = document.getElementById('tabTraceabilityContent');

    const storyMermaidContainer = document.getElementById('storyMermaidContainer');
    const fileTreeList = document.getElementById('fileTreeList');
    const activeCodeDisplay = document.getElementById('activeCodeDisplay');
    const workspacePreviewIframe = document.getElementById('workspacePreviewIframe');
    const storyMatrixTbody = document.getElementById('storyMatrixTbody');

    let currentProjectData = null;

    // 1. Fetch Dynamic Projects from Backend API
    async function loadDynamicProjects() {
        try {
            const resp = await fetch('/api/v1/projects');
            const data = await resp.json();
            renderProjectsGrid(data.projects || []);
        } catch (err) {
            console.warn('[Dynamic Load Notice]:', err.message);
            existingProjectsGrid.innerHTML = '<p class="text-muted">No projects found. Click "Create Project" to set up your first project.</p>';
        }
    }

    function renderProjectsGrid(projects) {
        projectCountBadge.textContent = `${projects.length} Project${projects.length === 1 ? '' : 's'}`;
        
        if (!projects || projects.length === 0) {
            existingProjectsGrid.innerHTML = `
                <div class="card story-ingestion-card" style="grid-column: 1 / -1; text-align: center; padding: 3rem 1.5rem;">
                    <h4>No Existing Projects Found</h4>
                    <p class="text-muted" style="margin: 0.5rem 0 1.5rem 0;">You haven't created any projects yet. Click "Create Project" to configure your tech stack.</p>
                    <button type="button" class="btn-primary" id="emptyStateCreateBtn" style="margin: 0 auto;">
                        <span class="btn-icon">✨</span> Create Your First Project
                    </button>
                </div>
            `;

            const emptyBtn = document.getElementById('emptyStateCreateBtn');
            if (emptyBtn) emptyBtn.addEventListener('click', openCreateModal);
            return;
        }

        let gridHtml = '';
        projects.forEach(p => {
            const cfg = p.config || {};
            const pid = cfg.projectId || "P001";
            gridHtml += `
                <div class="project-card" data-pid="${pid}">
                    <div class="card-title-row">
                        <span class="pid-tag">${pid}</span>
                        <h4>${cfg.projectName || 'Untitled Project'}</h4>
                    </div>
                    <p class="project-desc">${cfg.framework || 'React'} • ${cfg.language || 'TS'} • ${cfg.cssStrategy || 'Separate'} • ${cfg.folderStructure || 'Feature'}</p>
                    <div class="card-footer">
                        <span class="story-cnt">${p.storyCount || 0} Story/Stories</span>
                        <div style="display: flex; gap: 8px;">
                            <button type="button" class="btn-secondary btn-sm delete-project-btn" data-pid="${pid}" style="border-color: #ef4444; color: #ef4444;">🗑️</button>
                            <button type="button" class="btn-secondary btn-sm open-workspace-btn" data-pid="${pid}">Open Workspace →</button>
                        </div>
                    </div>
                </div>
            `;
        });

        existingProjectsGrid.innerHTML = gridHtml;

        // Attach click listeners to open dynamic workspace
        document.querySelectorAll('.open-workspace-btn, .project-card').forEach(elem => {
            elem.addEventListener('click', (e) => {
                if (e.target.closest('.delete-project-btn')) return; // Ignore if clicking delete button
                e.stopPropagation();
                const pid = elem.getAttribute('data-pid') || elem.closest('.project-card').getAttribute('data-pid');
                openProjectWorkspace(pid);
            });
        });

        // Attach click listeners for delete buttons
        document.querySelectorAll('.delete-project-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const pid = btn.getAttribute('data-pid');
                if (confirm(`Are you sure you want to delete Project ${pid}? This cannot be undone.`)) {
                    try {
                        const resp = await fetch(`/api/v1/projects/${pid}`, { method: 'DELETE' });
                        if (resp.ok) {
                            loadDynamicProjects(); // Refresh the grid
                        } else {
                            alert(`Failed to delete Project ${pid}`);
                        }
                    } catch (err) {
                        alert('Error deleting project: ' + err.message);
                    }
                }
            });
        });
    }

    // 2. Fetch Project Workspace Details Dynamically
    async function openProjectWorkspace(projectId) {
        try {
            const resp = await fetch(`/api/v1/projects/${projectId}`);
            if (!resp.ok) {
                alert(`Project '${projectId}' not found.`);
                return;
            }
            const data = await resp.json();
            currentProjectData = data;

            const cfg = data.config || {};
            activeProjectIdBadge.textContent = cfg.projectId || projectId;
            activeProjectTitle.textContent = cfg.projectName || 'Project Workspace';

            activeTechStackChips.innerHTML = `
                <span class="chip">${cfg.framework || 'React'}</span>
                <span class="chip">${cfg.language || 'TypeScript'}</span>
                <span class="chip">${cfg.cssStrategy || 'Separate CSS'}</span>
                <span class="chip">${cfg.folderStructure || 'Feature-based'}</span>
            `;

            projectsDashboardView.classList.add('hidden');
            projectWorkspaceView.classList.remove('hidden');
            backToProjectsBtn.classList.remove('hidden');

            renderWorkspaceData(data);

        } catch (err) {
            alert('Failed to load project details: ' + err.message);
        }
    }

    function renderWorkspaceData(data) {
        const stories = (data.storyGraph && data.storyGraph.stories) ? data.storyGraph.stories : [];
        const files = data.filesScanned || [];

        // Render Dynamic Story Dependency Graph
        renderStoryGraph(stories);

        // Render Dynamic File Tree
        renderFileTree(files);

        // Render Story Matrix
        renderStoryMatrix(stories);
    }

    function renderStoryGraph(stories) {
        if (!stories || stories.length === 0) {
            storyMermaidContainer.innerHTML = 'graph TD;\n  Start[Add Your First User Story]';
            return;
        }

        let lines = ['graph TD;'];
        lines.push('classDef node fill:#1e293b,stroke:#38bdf8,color:#f8fafc;');

        stories.forEach(s => {
            lines.push(`  ${s.id}["${s.id}: ${s.component}"]:::node;`);
            if (s.dependsOn && s.dependsOn.length > 0) {
                s.dependsOn.forEach(depId => {
                    lines.push(`  ${depId} --> ${s.id};`);
                });
            }
        });

        const code = lines.join('\n');
        if (window.mermaid) {
            storyMermaidContainer.innerHTML = code;
            storyMermaidContainer.removeAttribute('data-processed');
            window.mermaid.contentLoaded();
        }
    }

    function renderFileTree(files) {
        if (!files || files.length === 0) {
            fileTreeList.innerHTML = '<li class="text-muted">No files generated yet.</li>';
            return;
        }

        let html = '';
        files.forEach(f => {
            html += `<li class="file-item" data-path="${f}">📄 ${f}</li>`;
        });
        fileTreeList.innerHTML = html;

        document.querySelectorAll('.file-item').forEach(item => {
            item.addEventListener('click', () => {
                const path = item.getAttribute('data-path');
                activeCodeDisplay.textContent = `// File: ${path}\n// Displaying generated component code representation...`;
            });
        });
    }

    function renderStoryMatrix(stories) {
        if (!stories || stories.length === 0) {
            storyMatrixTbody.innerHTML = '<tr><td colspan="5">No user stories added yet.</td></tr>';
            return;
        }

        let html = '';
        stories.forEach(s => {
            const deps = (s.dependsOn && s.dependsOn.length > 0) ? s.dependsOn.join(', ') : 'None (Base Component)';
            html += `
                <tr>
                    <td><strong>${s.id}</strong></td>
                    <td>${s.title}</td>
                    <td><code>${s.component}</code></td>
                    <td><span class="dep-chip">${deps}</span></td>
                    <td><span class="status-chip chip-success">Generated & Connected</span></td>
                </tr>
            `;
        });
        storyMatrixTbody.innerHTML = html;
    }

    // 3. Add Incremental User Story Dynamically
    addStoryForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const storyText = newUserStory.value.trim();
        if (!storyText) {
            alert('Please enter a User Story description.');
            return;
        }

        const fileInput = document.getElementById('storyWireframeFile');
        if (!fileInput.files || fileInput.files.length === 0) {
            alert('A Wireframe image is mandatory. Please upload a wireframe image to continue.');
            return;
        }

        if (!currentProjectData || !currentProjectData.config) {
            alert('No active project workspace selected.');
            return;
        }

        const pid = currentProjectData.config.projectId;

        // Use FormData for file uploads instead of JSON
        const formData = new FormData();
        formData.append('userStory', storyText);
        formData.append('wireframe', fileInput.files[0]);

        try {
            const resp = await fetch(`/api/v1/projects/${pid}/stories`, {
                method: 'POST',
                body: formData
            });

            const result = await resp.json();
            console.log('[Incremental User Story Result]:', result);

            alert(`User Story ${result.storyId} generated!\nComponent: ${result.component}\nConnected to existing story graph.`);
            newUserStory.value = '';

            // Refresh workspace view dynamically
            openProjectWorkspace(pid);

        } catch (err) {
            alert('Failed to add story: ' + err.message);
        }
    });

    // 4. Create Project Wizard
    function openCreateModal() {
        createProjectModalOverlay.classList.remove('hidden');
        createProjectForm.reset();
    }

    function closeCreateModal() {
        createProjectModalOverlay.classList.add('hidden');
    }

    if (headerCreateProjectBtn) headerCreateProjectBtn.addEventListener('click', openCreateModal);
    if (closeCreateModalBtn) closeCreateModalBtn.addEventListener('click', closeCreateModal);
    if (cancelCreateBtn) cancelCreateBtn.addEventListener('click', closeCreateModal);

    createProjectForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const name = document.getElementById('newProjectName').value.trim();
        if (!name) {
            alert('Please enter a Project Name.');
            return;
        }

        const payload = {
            projectName: name,
            framework: document.getElementById('frameworkSelect').value,
            language: document.getElementById('languageSelect').value,
            cssStrategy: document.getElementById('cssStrategySelect').value,
            folderStructure: document.getElementById('folderStructureSelect').value
        };

        try {
            const resp = await fetch('/api/v1/projects', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await resp.json();
            closeCreateModal();

            // Refresh dashboard dynamically and open new project workspace
            await loadDynamicProjects();
            if (result.config && result.config.projectId) {
                openProjectWorkspace(result.config.projectId);
            }
        } catch (err) {
            alert('Failed to create project: ' + err.message);
        }
    });

    backToProjectsBtn.addEventListener('click', () => {
        projectWorkspaceView.classList.add('hidden');
        backToProjectsBtn.classList.add('hidden');
        projectsDashboardView.classList.remove('hidden');
        loadDynamicProjects();
    });

    // Tab Switching
    function switchTab(btn, content) {
        [tabStoryGraphBtn, tabCodeFilesBtn, tabLivePreviewBtn, tabTraceabilityBtn].forEach(b => b.classList.remove('active'));
        [tabStoryGraphContent, tabCodeFilesContent, tabLivePreviewContent, tabTraceabilityContent].forEach(c => c.classList.add('hidden'));

        btn.classList.add('active');
        content.classList.remove('hidden');
    }

    tabStoryGraphBtn.addEventListener('click', () => switchTab(tabStoryGraphBtn, tabStoryGraphContent));
    tabCodeFilesBtn.addEventListener('click', () => switchTab(tabCodeFilesBtn, tabCodeFilesContent));
    tabLivePreviewBtn.addEventListener('click', () => switchTab(tabLivePreviewBtn, tabLivePreviewContent));
    tabTraceabilityBtn.addEventListener('click', () => switchTab(tabTraceabilityBtn, tabTraceabilityContent));

    // Initial Dynamic Load
    loadDynamicProjects();
});
