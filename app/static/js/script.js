function switchTab(tabId) {
    const oldForm = document.querySelector('.auth-form.active');
    const newForm = document.getElementById('form-' + tabId);
    
    if (!oldForm || oldForm === newForm) return;

    // Update buttons
    document.getElementById('btn-login').classList.remove('active');
    document.getElementById('btn-signup').classList.remove('active');
    document.getElementById('btn-' + tabId).classList.add('active');

    const wrapper = document.getElementById('forms-wrapper');
    
    // Fix current height
    wrapper.style.height = oldForm.offsetHeight + 'px';
    
    // Crossfade old UI out
    oldForm.style.opacity = '0';
    oldForm.style.transform = 'translateY(-10px)';
    oldForm.style.transition = 'all 0.2s ease';
    
    setTimeout(() => {
        // Strip out old state
        oldForm.classList.remove('active');
        oldForm.style.opacity = '';
        oldForm.style.transform = '';
        oldForm.style.transition = '';
        
        // Prep new form measurement securely
        newForm.style.visibility = 'hidden';
        newForm.style.display = 'flex';
        newForm.style.position = 'absolute';
        
        const targetHeight = newForm.offsetHeight;
        
        // Strip inline hacks, prep for class-based layout
        newForm.style.visibility = '';
        newForm.style.display = '';
        newForm.style.position = '';
        
        // Add active to trigger the CSS keyframes gracefully
        newForm.classList.add('active');
        
        // Stretch or shrink the wrapper
        wrapper.style.height = targetHeight + 'px';
        
        // Release lock
        setTimeout(() => {
            wrapper.style.height = 'auto';
        }, 400); // Match CSS timer constraints
    }, 200); // Give previous form 200ms to visually leave
}

function selectRoleGrid(role) {
    // Hidden Input value update
    const selectedInput = document.getElementById('selected-role');
    if (selectedInput) selectedInput.value = role;

    // Toggle active classes on cards
    document.querySelectorAll('.role-choice-card').forEach(card => {
        card.classList.remove('active');
    });
    
    const clickedCard = document.getElementById('role-card-' + role);
    if (clickedCard) clickedCard.classList.add('active');

    // Proficiency Group Logic
    const profGroup = document.getElementById('proficiency-group');
    const profInput = document.getElementById('proficiency-input');
    
    if (profGroup && profInput) {
        if (role === 'player') {
            profGroup.classList.remove('hidden-group');
            profInput.setAttribute('required', 'true');
        } else {
            profGroup.classList.add('hidden-group');
            profInput.removeAttribute('required');
        }
    }
}

function togglePassword(inputId) {
    const input = document.getElementById(inputId);
    const icon = input.nextElementSibling;
    
    if (input.type === 'password') {
        input.type = 'text';
        icon.classList.remove('ph-eye');
        icon.classList.add('ph-eye-slash');
    } else {
        input.type = 'password';
        icon.classList.remove('ph-eye-slash');
        icon.classList.add('ph-eye');
    }
}

function nextSignupStep(currentStep) {
    // Validate current step inputs before moving forward
    const currentStepEl = document.getElementById('signup-step-' + currentStep);
    const inputs = currentStepEl.querySelectorAll('input, select');
    for (let i = 0; i < inputs.length; i++) {
        // Skip hidden proficiency input validation if not a player
        if(inputs[i].offsetParent === null) continue;
        
        if (!inputs[i].checkValidity()) {
            inputs[i].reportValidity();
            return;
        }
    }

    // Move to next step
    currentStepEl.classList.remove('active');
    const nextStepEl = document.getElementById('signup-step-' + (currentStep + 1));
    nextStepEl.classList.add('active');

    // Update Stepper Dots
    document.getElementById('step-ind-' + currentStep).classList.replace('active', 'completed');
    document.getElementById('step-ind-' + (currentStep + 1)).classList.add('active');
}

function prevSignupStep(currentStep) {
    // Move to previous step without validation
    const currentStepEl = document.getElementById('signup-step-' + currentStep);
    currentStepEl.classList.remove('active');
    
    const prevStepEl = document.getElementById('signup-step-' + (currentStep - 1));
    prevStepEl.classList.add('active');

    // Update Stepper Dots
    document.getElementById('step-ind-' + currentStep).classList.remove('active');
    const prevInd = document.getElementById('step-ind-' + (currentStep - 1));
    prevInd.classList.remove('completed');
    prevInd.classList.add('active');
}

function validateFinalStep() {
    const stepEl = document.getElementById('signup-step-3');
    const inputs = stepEl.querySelectorAll('input, select');
    for (let i = 0; i < inputs.length; i++) {
        if (!inputs[i].checkValidity()) {
            inputs[i].reportValidity();
            return false;
        }
    }
    return true;
}
