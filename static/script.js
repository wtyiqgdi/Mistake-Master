const API_BASE = '/api';

let currentPaperId = null;
let currentStudentId = null;
let questions = [];
let currentPracticeId = null;

function formatMathText(text) {
    let s = String(text ?? '');
    s = s
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    s = s.replace(/(\w)\^(\d+)/g, '$1<sup>$2</sup>');
    s = s.replace(/sqrt\(([^)]+)\)/gi, '&radic;($1)');
    s = s.replace(/\\sqrt\{([^}]+)\}/gi, '&radic;($1)');
    return s;
}

// DOM Elements
const loginView = document.getElementById('login-view');
const testView = document.getElementById('test-view');
const resultsView = document.getElementById('results-view');
const studentIdInput = document.getElementById('student-id');
const testModeSelect = document.getElementById('test-mode');
const equivalentOptions = document.getElementById('equivalent-options');
const startBtn = document.getElementById('start-btn');
const questionsContainer = document.getElementById('questions-container');
const submitBtn = document.getElementById('submit-btn');
const scoreSummary = document.getElementById('score-summary');
const feedbackContainer = document.getElementById('feedback-container');
const alertsContainer = document.getElementById('alerts-container');
const restartBtn = document.getElementById('restart-btn');

const practiceModal = document.getElementById('practice-modal');
const practiceContainer = document.getElementById('practice-question-container');
const practiceFeedback = document.getElementById('practice-feedback');
const submitPracticeBtn = document.getElementById('submit-practice-btn');
const closeModalBtn = document.querySelector('.close-btn');

// Event Listeners
startBtn.addEventListener('click', startTest);
submitBtn.addEventListener('click', submitTest);
restartBtn.addEventListener('click', () => location.reload());
testModeSelect.addEventListener('change', (e) => {
    if (e.target.value === 'equivalent') {
        equivalentOptions.classList.remove('hidden');
    } else {
        equivalentOptions.classList.add('hidden');
    }
});

closeModalBtn.addEventListener('click', () => practiceModal.classList.add('hidden'));
submitPracticeBtn.addEventListener('click', submitPractice);

async function startTest() {
    const studentId = studentIdInput.value.trim();
    if (!studentId) {
        alert('Please enter a Student ID');
        return;
    }
    currentStudentId = studentId;

    const mode = testModeSelect.value;
    const seed = document.getElementById('random-seed').value;
    
    const payload = {
        student_id: studentId,
        mode: mode,
        params: {}
    };
    
    if (mode === 'equivalent') {
        payload.seed = seed ? parseInt(seed) : null;
    }

    try {
        const response = await fetch(`${API_BASE}/paper/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Failed to create paper. Ensure Question Bank is frozen.');
        
        const data = await response.json();
        currentPaperId = data.paper_id;
        questions = data.questions;
        
        renderQuestions(questionsContainer, questions);
        switchView('test');
    } catch (err) {
        console.error(err);
        alert('Error starting test. ' + err.message);
    }
}

function renderQuestions(container, qs) {
    container.innerHTML = '';
    qs.forEach((q, index) => {
        const card = document.createElement('div');
        card.className = 'question-card';
        card.dataset.id = q.id;

        const stem = document.createElement('div');
        stem.className = 'question-stem';
        stem.innerHTML = `${index + 1}. ${formatMathText(q.stem)}`;
        card.appendChild(stem);

        const inputContainer = document.createElement('div');
        
        if (q.type === 'multiple_choice') {
            const optionsList = document.createElement('ul');
            optionsList.className = 'options-list';
            q.options.forEach(opt => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <label>
                        <input type="radio" name="q-${q.id}" value="${opt.id}">
                        ${opt.id}. ${formatMathText(opt.text)}
                    </label>
                `;
                optionsList.appendChild(li);
            });
            inputContainer.appendChild(optionsList);
        } else {
            inputContainer.innerHTML = `
                <input type="text" name="q-${q.id}" placeholder="Your answer...">
            `;
        }

        card.appendChild(inputContainer);
        container.appendChild(card);
    });
    if (window.MathJax && MathJax.typesetPromise) {
        MathJax.typesetPromise();
    }
}

async function submitTest() {
    const answers = {};
    let allAnswered = true;
    let answeredCount = 0;

    questions.forEach(q => {
        let val = '';
        if (q.type === 'multiple_choice') {
            const selected = document.querySelector(`input[name="q-${q.id}"]:checked`);
            if (selected) val = selected.value;
        } else {
            const input = document.querySelector(`input[name="q-${q.id}"]`);
            if (input) val = input.value.trim();
        }
        
        if (!val) allAnswered = false;
        if (val) answeredCount += 1;
        answers[q.id] = val;
    });

    if (answeredCount === 0) {
        alert("You must answer at least one question before submitting.");
        return;
    }

    if (!allAnswered && !confirm("Some questions are unanswered. Submit anyway?")) {
        return;
    }

    // Show loading
    submitBtn.textContent = "Grading...";
    submitBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE}/paper/${currentPaperId}/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: currentStudentId,
                answers: answers
            })
        });

        if (!response.ok) throw new Error('Failed to submit');
        
        const result = await response.json();
        renderResults(result);
        switchView('results');
    } catch (err) {
        console.error(err);
        alert('Error submitting test.');
        submitBtn.textContent = "Submit Answers";
        submitBtn.disabled = false;
    }
}

function renderResults(data) {
    scoreSummary.innerHTML = `
        <h3>Total Score: ${data.total_score} / ${data.total_questions}</h3>
    `;
    
    alertsContainer.innerHTML = '';
    if (data.repeated_errors && data.repeated_errors.length > 0) {
        data.repeated_errors.forEach(msg => {
            const alert = document.createElement('div');
            alert.className = 'alert-box';
            alert.textContent = msg;
            alertsContainer.appendChild(alert);
        });
    }

    feedbackContainer.innerHTML = '';
    
    data.results.forEach((item, index) => {
        const card = document.createElement('div');
        card.className = `result-card ${item.is_correct ? 'correct' : 'incorrect'}`;
        
        // Find question text
        const originalQ = questions.find(q => q.id === item.question_id);
        const stemText = originalQ ? originalQ.stem : item.question_id;

        let content = `
            <div class="question-stem">Q${index + 1}: ${formatMathText(stemText)}</div>
            <div>Your Answer: <strong>${item.student_answer || '(No Answer)'}</strong></div>
            <div>Status: ${item.is_correct ? 'Correct' : 'Wrong'}</div>
        `;

        if (!item.is_correct && item.error_analysis) {
            const analysis = item.error_analysis;
            content += `
                <div class="ai-feedback" id="analysis-${item.id}" data-level="${analysis.hint_level}">
                    <div><span class="feedback-label">Error Type:</span> ${analysis.primary_error_type}</div>
                    <div><span class="feedback-label">Explanation:</span> ${analysis.error_explanation}</div>
                    <div><span class="feedback-label">Hint (Level ${analysis.hint_level}):</span> ${analysis.hint}</div>
                    ${
                        analysis.recommended_knowledge_points && analysis.recommended_knowledge_points.length
                            ? `<div><span class="feedback-label">Knowledge Points:</span> ${analysis.recommended_knowledge_points.join(', ')}</div>`
                            : ''
                    }
                </div>
            `;

            if (analysis.hint_level < 3) {
                content += `<button class="secondary-btn" id="hint-btn-${item.id}" onclick="upgradeHint(${item.id})">Get Stronger Hint</button>`;
            }
            
            if (item.can_practice) {
                content += `<button class="practice-btn secondary-btn" onclick="startPractice(${item.id})">Practice Similar Question</button>`;
            }
        }

        card.innerHTML = content;
        feedbackContainer.appendChild(card);
    });
    if (window.MathJax && MathJax.typesetPromise) {
        MathJax.typesetPromise();
    }
}

function switchView(viewName) {
    loginView.classList.add('hidden');
    testView.classList.add('hidden');
    resultsView.classList.add('hidden');

    if (viewName === 'login') loginView.classList.remove('hidden');
    if (viewName === 'test') testView.classList.remove('hidden');
    if (viewName === 'results') resultsView.classList.remove('hidden');
}

// Practice Logic

async function startPractice(submissionItemId) {
    try {
        const response = await fetch(`${API_BASE}/practice/create`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: currentStudentId,
                original_submission_item_id: submissionItemId
            })
        });

        if (!response.ok) throw new Error('Failed to start practice');
        
        const data = await response.json();
        currentPracticeId = data.practice_id;
        const q = data.question;
        
        // Render Practice Question in Modal
        practiceContainer.innerHTML = '';
        practiceFeedback.classList.add('hidden');
        submitPracticeBtn.classList.remove('hidden');
        
        const card = document.createElement('div');
        card.className = 'question-card';
        card.innerHTML = `<div class="question-stem">${formatMathText(q.stem)}</div>`;
        
        const inputContainer = document.createElement('div');
        if (q.type === 'multiple_choice') {
            q.options.forEach(opt => {
                inputContainer.innerHTML += `
                    <div>
                        <label>
                            <input type="radio" name="practice-q" value="${opt.id}">
                            ${opt.id}. ${formatMathText(opt.text)}
                        </label>
                    </div>
                `;
            });
        } else {
            inputContainer.innerHTML = `<input type="text" name="practice-q" placeholder="Answer...">`;
        }
        
        card.appendChild(inputContainer);
        practiceContainer.appendChild(card);
        
        practiceModal.classList.remove('hidden');
        if (window.MathJax && MathJax.typesetPromise) {
            MathJax.typesetPromise();
        }
        
    } catch (err) {
        console.error(err);
        alert('Could not start practice session.');
    }
}

async function submitPractice() {
    let val = '';
    const radio = document.querySelector('input[name="practice-q"]:checked');
    const text = document.querySelector('input[name="practice-q"][type="text"]');
    
    if (radio) val = radio.value;
    if (text) val = text.value.trim();
    
    if (!val) {
        alert("Please answer.");
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/practice/${currentPracticeId}/submit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: currentStudentId,
                answer: val
            })
        });
        
        if (!response.ok) throw new Error('Failed to submit practice');
        
        const result = await response.json();
        
        practiceFeedback.innerHTML = `
            <div class="${result.is_correct ? 'correct' : 'incorrect'}" style="padding:10px; margin-top:10px;">
                <strong>${result.is_correct ? 'Correct!' : 'Incorrect'}</strong>
                <p>${result.feedback}</p>
            </div>
        `;
        practiceFeedback.classList.remove('hidden');
        submitPracticeBtn.classList.add('hidden');
        
    } catch (err) {
        console.error(err);
        alert('Error submitting practice.');
    }
}

async function upgradeHint(submissionItemId) {
    const analysisBox = document.getElementById(`analysis-${submissionItemId}`);
    const btn = document.getElementById(`hint-btn-${submissionItemId}`);
    if (!analysisBox || !btn) return;

    const currentLevel = parseInt(analysisBox.dataset.level || '1', 10);
    const nextLevel = Math.min(3, currentLevel + 1);
    if (nextLevel === currentLevel) return;

    btn.disabled = true;
    const prevText = btn.textContent;
    btn.textContent = 'Loading...';

    try {
        const response = await fetch(`${API_BASE}/submission/items/${submissionItemId}/hint`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id: currentStudentId,
                hint_level: nextLevel
            })
        });
        if (!response.ok) throw new Error('Failed to upgrade hint');

        const analysis = await response.json();
        analysisBox.dataset.level = analysis.hint_level;
        analysisBox.innerHTML = `
            <div><span class="feedback-label">Error Type:</span> ${analysis.primary_error_type}</div>
            <div><span class="feedback-label">Explanation:</span> ${analysis.error_explanation}</div>
            <div><span class="feedback-label">Hint (Level ${analysis.hint_level}):</span> ${analysis.hint}</div>
            ${
                analysis.recommended_knowledge_points && analysis.recommended_knowledge_points.length
                    ? `<div><span class="feedback-label">Knowledge Points:</span> ${analysis.recommended_knowledge_points.join(', ')}</div>`
                    : ''
            }
        `;

        if (analysis.hint_level >= 3) {
            btn.classList.add('hidden');
        } else {
            btn.disabled = false;
            btn.textContent = prevText;
        }
    } catch (err) {
        console.error(err);
        btn.disabled = false;
        btn.textContent = prevText;
        alert('Could not upgrade hint.');
    }
}
