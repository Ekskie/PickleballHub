function switchTab(tabId) {
    // Update buttons
    document.getElementById('btn-login').classList.remove('active');
    document.getElementById('btn-signup').classList.remove('active');
    document.getElementById('btn-' + tabId).classList.add('active');

    // Update forms
    document.getElementById('form-login').classList.remove('active');
    document.getElementById('form-signup').classList.remove('active');
    document.getElementById('form-' + tabId).classList.add('active');
}

function selectRole(element, role) {
    // Remove active class from all roles
    document.querySelectorAll('.role-card').forEach(el => el.classList.remove('active'));
    // Add active class to clicked role
    element.classList.add('active');
    // Update hidden input
    document.getElementById('selected-role').value = role;
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
