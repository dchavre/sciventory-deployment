document.addEventListener('DOMContentLoaded', () => {
    const table = document.getElementById('data-table');
    const addRowBtn = document.getElementById('add-row');
    const saveTableBtn = document.getElementById('save-table');

    // Add a new row
    addRowBtn.addEventListener('click', () => {
        const tbody = table.querySelector('tbody');
        const newRow = document.createElement('tr');

        for (let i = 0; i < table.rows[0].cells.length - 1; i++) {
            const newCell = document.createElement('td');
            newCell.contentEditable = "true";
            newCell.innerText = "";
            newRow.appendChild(newCell);
        }

        const actionsCell = document.createElement('td');
        const deleteBtn = document.createElement('button');
        deleteBtn.classList.add('delete-row');
        deleteBtn.innerHTML = "&times";
        deleteBtn.addEventListener('click', () => newRow.remove());
        actionsCell.appendChild(deleteBtn);

        newRow.appendChild(actionsCell);
        tbody.insertBefore(newRow, tbody.firstChild)
    });

    // Save table data
    saveTableBtn.addEventListener('click', () => {
        const rows = Array.from(table.querySelectorAll('tbody tr'));
        const data = rows.map(row => 
            Array.from(row.cells).slice(0, -1).map(cell => cell.innerText)
        );

        fetch('/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ data })
        })
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(err => alert('Error saving data!'));
    });

    // Delete a row
    table.addEventListener('click', (e) => {
        if (e.target.classList.contains('delete-row')) {
            e.target.closest('tr').remove();
        }
    });
});


