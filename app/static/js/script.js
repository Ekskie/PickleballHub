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

function toggleRoleDropdown() {
    const opts = document.getElementById('role-dropdown-opts');
    if(opts) {
        opts.classList.toggle('open');
        const caret = document.getElementById('role-caret');
        if(caret) caret.classList.toggle('rotated');
    }
}

function selectRoleDropdown(role, iconClass, title, desc) {
    // Update Trigger UI
    document.getElementById('selected-role-icon').className = 'ph ' + iconClass;
    document.getElementById('selected-role-title').innerText = title;
    document.getElementById('selected-role-desc').innerText = desc;
    
    // Update hidden input
    document.getElementById('selected-role').value = role;
    
    // Close dropdown
    document.getElementById('role-dropdown-opts').classList.remove('open');
    const caret = document.getElementById('role-caret');
    if(caret) caret.classList.remove('rotated');

    // Handle proficiency
    const profGroup = document.getElementById('proficiency-group');
    const profInput = document.getElementById('proficiency-input');
    if (profGroup) {
        if (role === 'player') {
            profGroup.classList.remove('hidden-group');
            if (profInput) profInput.setAttribute('required', 'true');
        } else {
            profGroup.classList.add('hidden-group');
            if (profInput) profInput.removeAttribute('required');
        }
    }
}

// Close dropdown when clicking outside
document.addEventListener('click', function(event) {
    const trigger = document.querySelector('.custom-select-trigger');
    const opts = document.getElementById('role-dropdown-opts');
    if (trigger && opts) {
        if (!trigger.contains(event.target) && !opts.contains(event.target)) {
            opts.classList.remove('open');
            const caret = document.getElementById('role-caret');
            if(caret) caret.classList.remove('rotated');
        }
    }
});

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
