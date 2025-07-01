/**
 * Creates a new sheet for managing Basket % Allocations for accounts.
 * The sheet allows viewing and editing Basket % Allocations with selectable rows.
 */
function viewBasketAllocations() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();

  try {
    // Log the beginning of the sheet setup
    logAction(
      "Create Sheet",
      "Basket % Allocations",
      "",
      "",
      "",
      "Started",
      "Creating or clearing the 'Basket % Allocations' sheet",
      "INFO"
    );

    // Create or clear the 'Basket % Allocations' sheet
    let sheet = ss.getSheetByName("Basket % Allocations");
    if (!sheet) {
      sheet = ss.insertSheet("Basket % Allocations");
      logAction(
        "Create Sheet",
        "Basket % Allocations",
        "",
        "",
        "",
        "Success",
        "Created new 'Basket % Allocations' sheet",
        "INFO"
      );
    } else {
      sheet.clear();
      logAction(
        "Clear Sheet",
        "Basket % Allocations",
        "",
        "",
        "",
        "Success",
        "Cleared existing 'Basket % Allocations' sheet",
        "INFO"
      );
    }

    // Fetch allocation data from backend
    const endpoint = "http://15.207.59.232:8000/account-allocations/sheet-data";
    let responseData;
    try {
      const response = UrlFetchApp.fetch(endpoint, { muteHttpExceptions: true });
      const statusCode = response.getResponseCode();
      
      if (statusCode !== 200) {
        logAction(
          "Fetch Data",
          "Basket % Allocations",
          "",
          "",
          "",
          "Failed",
          `Failed to fetch data: Status code ${statusCode}`,
          "ERROR"
        );
        throw new Error(`Failed to fetch allocation data: Status code ${statusCode}`);
      }

      responseData = JSON.parse(response.getContentText());
      logAction(
        "Fetch Data",
        "Basket % Allocations",
        "",
        "",
        "",
        "Success",
        `Fetched allocation data for ${responseData.data.length - 3} accounts`,
        "INFO"
      );
    } catch (error) {
      logError("viewBasketAllocations:fetchData", error);
      ui.alert("Error fetching allocation data: " + error.message);
      return;
    }

    // Get the data and basket information
    const sheetData = responseData.data;
    const baskets = responseData.baskets;
    
    // Remove the second row from the API data (old instructions)
    // Keep the first row for our new instructions and the third row for column headers
    if (sheetData.length > 2) {
      sheetData.splice(1, 1); // Remove the second row (index 1)
    }
    
    // Let's print some debug information to understand the structure
    console.log(`Data rows after removing old instructions: ${sheetData.length}`);
    if (sheetData.length > 0) {
      console.log(`First row columns: ${sheetData[0].length}`);
    }
    if (sheetData.length > 2) {
      console.log(`Header row columns: ${sheetData[2].length}`);
    }
    
    // Find the maximum number of columns across all rows
    let maxColumns = 0;
    for (let i = 0; i < sheetData.length; i++) {
      maxColumns = Math.max(maxColumns, sheetData[i].length);
    }
    console.log(`Maximum columns found: ${maxColumns}`);
    
    // Ensure all rows have the same number of columns (using the maximum found)
    for (let i = 0; i < sheetData.length; i++) {
      const currentRow = sheetData[i];
      // Add empty cells to make all rows the same length
      while (currentRow.length < maxColumns) {
        currentRow.push("");
      }
    }
    
    // Double-check that all rows now have the same length
    for (let i = 0; i < sheetData.length; i++) {
      if (sheetData[i].length !== maxColumns) {
        throw new Error(`Row ${i} has ${sheetData[i].length} columns, expected ${maxColumns}`);
      }
    }
    
    // Now write all data to the sheet with the consistent number of columns
    sheet.getRange(1, 1, sheetData.length, maxColumns).setValues(sheetData);
    
    // Format header row - With single merged cell for instructions (removing title row)
    // Merge the first row into a single cell for instructions
    sheet.getRange(1, 1, 1, maxColumns).merge();
    const headerRow1 = sheet.getRange(1, 1, 1, 1);
    headerRow1.setValue("Instructions:\n• Check the 'Select' checkbox for accounts you want to update\n• Modify the basket allocation percentages\n• The total allocation should equal 100%\n• Click 'Save Allocation Changes' button when done");
    headerRow1.setBackground("#000000");
    headerRow1.setFontColor("#FFFFFF");
    headerRow1.setFontWeight("bold");
    headerRow1.setFontSize(11);
    headerRow1.setHorizontalAlignment("left");
    headerRow1.setVerticalAlignment("middle");
    headerRow1.setWrap(true);
    
    // Format the second row (column headers)
    const headerRow2 = sheet.getRange(2, 1, 1, maxColumns);
    headerRow2.setBackground("#91B9F9");
    headerRow2.setFontWeight("bold");
    headerRow2.setHorizontalAlignment("center");
    
    // Format data rows with alternating colors
    const dataRows = sheetData.length - 2; // Subtract 2 header rows (no title row)
    for (let i = 0; i < dataRows; i++) {
      const rowIndex = i + 3; // Start from row 3 (after instructions and headers)
      const rowRange = sheet.getRange(rowIndex, 1, 1, sheetData[0].length);
      
      if (i % 2 === 0) {
        rowRange.setBackground("#FFFFFF");
      } else {
        rowRange.setBackground("#F3F3F3");
      }
    }
    
    // Freeze the header rows
    sheet.setFrozenRows(2);
    
    // Set column widths
    sheet.setColumnWidth(1, 80);  // Select checkbox
    sheet.setColumnWidth(2, 120); // Account ID
    sheet.setColumnWidth(3, 180); // Account Name
    sheet.setColumnWidth(4, 100); // Account Type
    sheet.setColumnWidth(5, 120); // Broker Name
    sheet.setColumnWidth(6, 100); // Broker Code
    sheet.setColumnWidth(7, 180); // Portfolio Name
    sheet.setColumnWidth(8, 120); // Bracket Name
    sheet.setColumnWidth(9, 120); // Total % Allocation
    
    // Set width for basket columns
    for (let i = 0; i < baskets.length; i++) {
      sheet.setColumnWidth(10 + i, 120);
    }
    
    sheet.setColumnWidth(10 + baskets.length, 150); // Updated At
    
    // Create checkboxes in the 'Select' column
    // After removing the old instructions row, data rows start at row 3
    const dataStartRow = 3; // First data row (after headers)
    const checkboxRange = sheet.getRange(dataStartRow, 1, dataRows);
    const checkboxRule = SpreadsheetApp.newDataValidation()
      .requireCheckbox()
      .build();
    checkboxRange.setDataValidation(checkboxRule);
    
    // Add data validation for allocation percentages to ensure they're numeric
    // This applies to all basket columns dynamically determined from the first row
    
    // Extract basket names directly from the first row of data
    const firstRowData = sheetData[0]; // First row contains column headers with basket names
    const basketNames = [];
    
    // Skip the first placeholder ("Basket % Allocations") and the last ("Updated At")
    // All other non-empty values in between the standard columns are basket names
    const startIndex = 9; // Index after standard columns (Select, ID, Name, Type, Portfolio, Bracket, Total, Broker Name, Broker Code)
    const endIndex = firstRowData.length - 1; // Index before "Updated At"

    for (let i = startIndex; i < endIndex; i++) {
      const columnName = firstRowData[i];
      if (columnName && columnName.trim() !== "") {
        basketNames.push({
          index: i,
          name: columnName
        });
      }
    }
    
    console.log('Found basketNames: ', basketNames);
    console.log(`Found ${basketNames.length} baskets directly from header row`);
    basketNames.forEach(b => console.log(`- ${b.name} (column ${b.index})`));
    
    // Format all basket columns as percentages
    // Note: dataStartRow is already declared above, don't redeclare it here
    basketNames.forEach(basket => {

      const colIndex = basket.index + 1;
      const allocRange = sheet.getRange(dataStartRow, colIndex, dataRows);
      
      let allocValues1 = allocRange.getValues();

      // Format as percentage
      allocRange.setNumberFormat("0.00%");
      
      // Convert decimal values to percentages
      const allocValues = allocRange.getValues();
      for (let r = 0; r < allocValues.length; r++) {
        if (typeof allocValues[r][0] === 'number' || !isNaN(parseFloat(allocValues[r][0]))) {
          // Handle both number types and string numbers
          let numValue = typeof allocValues[r][0] === 'number' ? 
              allocValues[r][0] : parseFloat(allocValues[r][0]);
              
          allocValues[r][0] = numValue / 100;
        }
      }
      allocRange.setValues(allocValues);

      // Double-check formatting by applying it directly to each cell
      for (let r = 0; r < dataRows; r++) {
        sheet.getRange(dataStartRow + r, colIndex).setNumberFormat("0.00%");
      }
    });
    
    // Format the 'Total % Allocation' column as percentage
    const totalAllocRange = sheet.getRange(dataStartRow, 9, dataRows);
    totalAllocRange.setNumberFormat("0.00%");
    
    // Convert decimal values to percentages (multiply by 100)
    const totalValues = totalAllocRange.getValues();
    for (let r = 0; r < totalValues.length; r++) {
      if (typeof totalValues[r][0] === 'number') {
        totalValues[r][0] = totalValues[r][0] / 100;
      }
    }
    totalAllocRange.setValues(totalValues);
    
    // Color the Total % Allocation based on whether it equals 100%
    for (let i = 0; i < dataRows; i++) {
      const rowIndex = dataStartRow + i;
      const totalCell = sheet.getRange(rowIndex, 7);
      const totalValue = totalCell.getValue() * 100; // Convert from percentage format
      
      if (Math.abs(totalValue - 100) < 0.01) {
        totalCell.setBackground("#C6EFCE"); // Green for 100%
      } else if (totalValue > 100) {
        totalCell.setBackground("#FFC7CE"); // Red for > 100%
      } else if (totalValue < 100) {
        totalCell.setBackground("#FFEB9C"); // Yellow for < 100%
      }
    }
    
    // Store basket information in a hidden row for reference when saving
    const hiddenRow = sheet.getLastRow() + 2;
    sheet.getRange(hiddenRow, 1).setValue("HIDDEN_BASKET_INFO");
    sheet.getRange(hiddenRow, 2).setValue(JSON.stringify(baskets));
    sheet.hideRows(hiddenRow);
    
    // Activate the sheet
    sheet.activate();
    
    // Log completion
    logAction(
      "Create Sheet",
      "Basket % Allocations",
      "",
      "",
      "",
      "Completed",
      "Basket % Allocations sheet successfully populated",
      "INFO"
    );
    
    // Show success message
    // ui.alert(
    //   "Basket % Allocations Sheet Ready",
    //   "Check the boxes in the 'Select' column for accounts you want to update, modify allocation percentages, then click 'Save Allocation Changes'.",
    //   ui.ButtonSet.OK
    // );
  } catch (error) {
    // Log any errors
    logError("viewBasketAllocations", error);
    ui.alert("Error creating Basket % Allocations sheet: " + error.message);
  }
}

/**
 * Saves changes made to the Basket % Allocations sheet.
 * Only rows with the 'Select' checkbox checked will be processed.
 */
function saveBasketAllocationChanges() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const ui = SpreadsheetApp.getUi();
  const sheet = ss.getSheetByName("Basket % Allocations");
  
  if (!sheet) {
    ui.alert("Basket % Allocations sheet not found.");
    logAction(
      "Save Changes",
      "Basket % Allocations",
      "",
      "",
      "",
      "Failed",
      "Basket % Allocations sheet not found",
      "ERROR"
    );
    return;
  }
  
  try {
    // Get the number of rows and columns in the sheet
    const lastRow = sheet.getLastRow();
    const lastCol = sheet.getLastColumn();
    
    if (lastRow < 4) {
      // No data rows after header rows
      ui.alert("No account data found in the sheet.");
      return;
    }
    
    // Get all data from the sheet
    const allData = sheet.getRange(1, 1, lastRow, lastCol).getValues();
    
    // Extract header row to identify columns
    const headerRow = allData[1]; // The second row contains column headers
    
    // Find the indices of important columns
    const selectColIndex = headerRow.indexOf("Select");
    const accountIdColIndex = headerRow.indexOf("Account ID");
    const accountNameColIndex = headerRow.indexOf("Account Name");
    const accountTypeColIndex = headerRow.indexOf("Account Type");
    const portfolioNameColIndex = headerRow.indexOf("Portfolio Name");
    const bracketNameColIndex = headerRow.indexOf("Bracket Name");
    const totalAllocColIndex = headerRow.indexOf("Total % Allocation");
    const brokerNameColIndex = headerRow.indexOf("Broker Name");
    const brokerCodeColIndex = headerRow.indexOf("Broker Code");
    const updatedAtColIndex = headerRow.indexOf("Updated At");
    
    // Make sure we found all required columns
    if (selectColIndex === -1 || accountIdColIndex === -1 || accountTypeColIndex === -1) {
      ui.alert("Required columns not found in the sheet. Please refresh the sheet and try again.");
      return;
    }
    
    // Find basket columns
    const basketCols = [];
    for (let i = 0; i < headerRow.length; i++) {
      const colName = headerRow[i];
      // Skip standard columns - basket columns are between broker code and updated at
      if (i > brokerCodeColIndex && i < updatedAtColIndex && colName && colName.trim() !== "") {
        basketCols.push({
          index: i,
          name: colName
        });
      }
    }

    console.log(`Found ${basketCols.length} basket columns`);
    basketCols.forEach(b => console.log(`- ${b.name} (column ${b.index})`));
    
    // Prepare the data to send to the server - NEW FORMAT as array of objects
    const selectedRows = [];
    
    // Iterate through data rows (starting from row 3, index 2)
    for (let i = 2; i < allData.length; i++) {
      const row = allData[i];
      
      // Check if this row is selected (checkbox is checked)
      if (row[selectColIndex] === true) {
        // Create a JSON object for each row
        const rowObject = {
          "Select": false, // Set to false in the request format
          "Account ID": row[accountIdColIndex],
          "Account Name": row[accountNameColIndex],
          "Account Type": row[accountTypeColIndex],
          "Broker Name": row[brokerNameColIndex],
          "Broker Code": row[brokerCodeColIndex],
          "Portfolio Name": row[portfolioNameColIndex],
          "Bracket Name": row[bracketNameColIndex],
          "Total % Allocation": formatPercentage(row[totalAllocColIndex])
        };
        
        // Add basket allocation values
        basketCols.forEach(basket => {
          rowObject[basket.name] = formatPercentage(row[basket.index]);
        });
        
        // Add updated at column (null for new entries)
        rowObject["Updated At"] = row[updatedAtColIndex] || null;
        
        selectedRows.push(rowObject);
      }
    }
    
    if (selectedRows.length === 0) {
      ui.alert("No rows selected for update.");
      return;
    }
    
    // Log that we're sending updates
    logAction(
      "Save Changes",
      "Basket % Allocations",
      "",
      "",
      "",
      "Started",
      `Sending ${selectedRows.length} account allocation updates`,
      "INFO"
    );
    
    // Send the data to the backend in the new format
    const endpoint = "http://15.207.59.232:8000/account-allocations/sheet-update";
    const payload = {
      data: selectedRows
    };
    
    // For debugging: log what we're sending
    console.log("Sending payload to backend:");
    console.log(JSON.stringify(payload));
    
    const options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    };
    
    const response = UrlFetchApp.fetch(endpoint, options);
    const statusCode = response.getResponseCode();
    
    if (statusCode !== 200) {
      const errorText = response.getContentText();
      logAction(
        "Save Changes",
        "Basket % Allocations",
        "",
        "",
        "",
        "Failed",
        `Error saving allocation changes: ${errorText}`,
        "ERROR"
      );
      ui.alert(`Error saving allocation changes: ${errorText}`);
      return;
    }
    
    // Parse the response
    const result = JSON.parse(response.getContentText());
    
    // Log success
    logAction(
      "Save Changes",
      "Basket % Allocations",
      "",
      "",
      "",
      "Success",
      `Successfully processed allocation updates`,
      "INFO"
    );
    
    // Show a success message
    ui.alert("Allocation updates completed successfully!");
    
    // Refresh the sheet to show the updated data
    viewBasketAllocations();
    
  } catch (error) {
    // Log any errors
    logError("saveBasketAllocationChanges", error);
    ui.alert("Error saving allocation changes: " + error.message);
  }
}

/**
 * Handles editing of allocation percentages in the Basket Allocations sheet.
 * Triggered automatically when a cell is edited.
 */
function onEdit(e) {
  // Check if the edit was in the Basket Allocations sheet
  const sheet = e.source.getActiveSheet();
  if (sheet.getName() !== "Basket % Allocations") return;
  
  // Get the edited cell
  const editedCell = e.range;
  const row = editedCell.getRow();
  const col = editedCell.getColumn();
  
  // Only process edits to data rows (after headers)
  if (row <= 2) return;
  
  try {
    // Get the first row which contains column headers including basket names
    const firstRow = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
    
    // Get the header row with actual column labels
    const headerRow = sheet.getRange(2, 1, 1, sheet.getLastColumn()).getValues()[0];
    
    // Find total % allocation column
    const totalAllocColIndex = headerRow.indexOf("Total % Allocation") + 1; // +1 because sheet columns are 1-based
    if (totalAllocColIndex === 0) return; // Not found
    
    // Find basket columns by looking at the first row
    // Basket columns are between standard columns and Updated At
    const startIndex = 9; // Index after standard columns (Select, ID, Name, Type, Portfolio, Bracket, Total, Broker Name, Broker Code)
    const endIndex = headerRow.indexOf("Updated At");
    
    if (endIndex === -1) return; // Updated At column not found
    
    // Create array of basket column indices (1-based for sheet columns)
    const basketCols = [];
    for (let i = startIndex; i < endIndex; i++) {
      if (headerRow[i] && headerRow[i].trim() !== "") {
        basketCols.push(i + 1); // +1 because sheet columns are 1-based
      }
    }
    
    // Only process if column is a basket column
    if (basketCols.length === 0 || !basketCols.includes(col)) return;
    
    // Calculate total allocation for the row
    let total = 0;
    
    basketCols.forEach(c => {
      const value = sheet.getRange(row, c).getValue();
      if (typeof value === 'number') {
        total += value * 100; // Convert from percentage format
      } else if (typeof value === 'string') {
        // Handle string values (user might enter "13%" or "13")
        let strValue = value.trim();
        if (strValue.endsWith('%')) {
          strValue = strValue.substring(0, strValue.length - 1);
        }
        const numValue = parseFloat(strValue);
        if (!isNaN(numValue)) {
          total += numValue;
        }
      }
    });
    
    // Update the total cell
    const totalCell = sheet.getRange(row, totalAllocColIndex);
    totalCell.setValue(total / 100); // Convert back to percentage format
    
    // Format the total cell based on the value
    if (Math.abs(total - 100) < 0.01) {
      totalCell.setBackground("#C6EFCE"); // Green for 100%
    } else if (total > 100) {
      totalCell.setBackground("#FFC7CE"); // Red for > 100%
    } else if (total < 100) {
      totalCell.setBackground("#FFEB9C"); // Yellow for < 100%
    }
  } catch (error) {
    console.error("Error in onEdit: " + error.message);
  }
}

/**
 * Helper function to format percentage values consistently
 * @param {any} value - The percentage value to format
 * @return {string} - Formatted percentage string (e.g. "19.70%")
 */
function formatPercentage(value) {
  if (typeof value === 'number') {
    // Convert from decimal (0.197) to percentage string ("19.70%")
    return (value * 100).toFixed(2) + '%';
  } else if (typeof value === 'string') {
    // Handle string values (e.g., "13%")
    value = value.trim();
    if (!value.endsWith('%')) {
      // If no % sign, add it
      const numValue = parseFloat(value);
      if (!isNaN(numValue)) {
        return numValue.toFixed(2) + '%';
      }
    } else {
      // If already has % sign, ensure it has 2 decimal places
      const numStr = value.substring(0, value.length - 1);
      const numValue = parseFloat(numStr);
      if (!isNaN(numValue)) {
        return numValue.toFixed(2) + '%';
      }
    }
    return value; // Return original if parsing failed
  }
  
  // Default for empty or undefined values
  return "0.00%";
}
