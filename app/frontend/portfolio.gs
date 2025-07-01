function openStandardPortfolioSheet() {
  portfolioId = 1 // Standard Portfolio
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheetName = "Standard Portfolio";
  let sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
  }
  sheet.clear();
  const url = "http://15.207.59.232:8000/portfolios/" + portfolioId + "/structure";
  const options = { muteHttpExceptions: true };
  const resp = UrlFetchApp.fetch(url, options);
  if (resp.getResponseCode() != 200) {
    SpreadsheetApp.getUi().alert("Error fetching portfolio structure: " + resp.getContentText());
    return;
  }
  const data = JSON.parse(resp.getContentText());
  renderBracketBasketSheet(sheet, data);
}

function renderBracketBasketSheet(sheet, data) {
  // Write JSON output for debugging
  // var sheet1 = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Standard Portfolio");
  // sheet1.getRange("F50").setValue(JSON.stringify(data, null, 2));

  // TITLE: Basket & Bracket Allocation
  let totalColumns = 14;
  let titleRange = sheet.getRange(1, 1, 1, totalColumns);
  titleRange.merge();
  titleRange.setBackground("#2E2E2E");
  titleRange.setFontColor("#FFFFFF");
  titleRange.setFontWeight("bold");
  titleRange.setHorizontalAlignment("center");
  titleRange.setValue("Basket & Bracket Allocation");

  // INSTRUCTIONS FOR BASKETS AND BRACKETS
  let notesRow = 2;
  let notesRange = sheet.getRange(notesRow, 1, 1, totalColumns);
  notesRange.merge();
  notesRange.setBackground("#000000");
  notesRange.setFontColor("#FFFFFF");
  notesRange.setFontWeight("bold");
  notesRange.setVerticalAlignment("middle");
  let notesText = `*** Add Baskets and Brackets to the next of the rows and columns respectively. ***

  NOTES:

  1. Addition of a Text below the last row of Bracket cell and Text on right side of the Basket cell will create a new bracket and basket respectively with 0% Allocation if no values are added.
  2. If the name of the bracket or basket is left empty during creation, it will be named "Bracket_1", "Basket_2". Naming the Brackets and Baskets is highly recommended.
  3. Deleting all the values from a row with the name of Bracket will delete that Bracket! Same goes for Baskets for columns.`;
  notesRange.setValue(notesText);

  // HEADER ROW FOR BRACKETS AND BASKETS
  let rowOffset = 4;
  let headerRange = sheet.getRange(rowOffset, 1, 1, totalColumns);
  headerRange.setFontWeight("bold");

  // Set headers for bracket section
  let headers = ["Bracket Name", "Min Amount", "Max Amount"];
  for (let i = 0; i < headers.length; i++) {
    let cell = sheet.getRange(rowOffset, i + 1);
    cell.setValue(headers[i]);
    cell.setBackground("#91B9F9");
    cell.setFontWeight("bold");
    cell.setHorizontalAlignment("center");
  }

  // Set headers for basket section (basket names and their IDs in a hidden row)
  let basketStartCol = 4;
  // Write basket names in header row and their IDs in row 4 (hidden)
  for (let i = 0; i < data.baskets.length; i++) {
    let col = basketStartCol + i;
    let basketCell = sheet.getRange(rowOffset, col);
    basketCell.setValue(data.baskets[i].basket_name);
    basketCell.setBackground("#91B9F9");
    basketCell.setFontWeight("bold");
    basketCell.setHorizontalAlignment("center");
    // Write basket_id into row 1000, then hide row 1000 later if desired.
    let idCell = sheet.getRange(1000, col);
    idCell.setValue(data.baskets[i].basket_id);
    idCell.setFontSize(1);
    idCell.setFontColor("#FFFFFF");
  }

  // Write bracket rows (including bracket IDs in a hidden column)
  let rowStart = rowOffset + 1;
  for (let r = 0; r < data.brackets.length; r++) {
    let bracketRow = rowStart + r;
    sheet.getRange(bracketRow, 1).setValue(data.brackets[r].bracket_name).setBackground("#BCD4FC").setFontWeight("bold");
    sheet.getRange(bracketRow, 2).setValue(data.brackets[r].min_amount).setBackground("#BCD4FC").setFontWeight("bold");
    sheet.getRange(bracketRow, 3).setValue(data.brackets[r].max_amount).setBackground("#BCD4FC").setFontWeight("bold");
    sheet.getRange(bracketRow, 1, 1, 3).setHorizontalAlignment("center");
    // Write bracket_id in hidden column 50
    sheet.getRange(bracketRow, 50).setValue(data.brackets[r].bracket_id).setFontColor("#FFFFFF");
  }

  // Populate Basket Allocations using bracket_id and basket_id as key
  let bracketsArr = data.brackets;
  let basketsArr = data.baskets;
  let allocations = data.allocations;
  for (let r = 0; r < bracketsArr.length; r++) {
    for (let c = 0; c < basketsArr.length; c++) {
      let bracketId = bracketsArr[r].bracket_id;
      let basketId = basketsArr[c].basket_id;
      let key = `${bracketId},${basketId}`;
      let allocationValue = allocations[key] || 0;
      let targetCell = sheet.getRange(rowStart + r, basketStartCol + c);
      targetCell.setValue(allocationValue);
      targetCell.setHorizontalAlignment("center");
    }
  }

  // Leave 6 blank rows after the allocation table
  let secondTitleRow = rowStart + data.brackets.length + 6;
  let secondTitleRange = sheet.getRange(secondTitleRow, 1, 1, totalColumns);
  secondTitleRange.merge();
  secondTitleRange.setBackground("#800000");
  secondTitleRange.setFontColor("#FFFFFF");
  secondTitleRange.setFontWeight("bold");
  secondTitleRange.setHorizontalAlignment("center");
  secondTitleRange.setValue("Do not fill Brackets beyond this buffer line, please save the current additions first, reload the sheet and then add the remaining Baskets.");

  // Two blank merged rows with light maroon red background
  let blankRow1 = secondTitleRow + 1;
  let blankRow2 = blankRow1 + 1;
  sheet.getRange(blankRow1, 1, 1, totalColumns).merge().setBackground("#C06060");
  sheet.getRange(blankRow2, 1, 1, totalColumns).merge().setBackground("#C06060");

  // Basket & Stock Multiplier Allocation title row
  let multiplierTitleRow = blankRow2 + 1;
  let multiplierTitleRange = sheet.getRange(multiplierTitleRow, 1, 1, totalColumns);
  multiplierTitleRange.merge();
  multiplierTitleRange.setBackground("#2E2E2E");
  multiplierTitleRange.setFontColor("#FFFFFF");
  multiplierTitleRange.setFontWeight("bold");
  multiplierTitleRange.setHorizontalAlignment("center");
  multiplierTitleRange.setValue("Basket & Stock Multiplier Allocation");

  // Instructions row for basket stocks
  let instructionsRow = multiplierTitleRow + 1;
  let instructionsRange = sheet.getRange(instructionsRow, 1, 1, totalColumns);
  instructionsRange.merge();
  instructionsRange.setBackground("#000000");
  instructionsRange.setFontColor("#FFFFFF");
  instructionsRange.setFontWeight("bold");
  instructionsRange.setVerticalAlignment("middle");
  let instructionsText = `*** Strict Instructions to follow! ***

  1. Use Trading symbols from Dhan Master file.
  2. Keep a space of one** column in between 2 tables as already formatted below.
  3. Basket name must** match with the name of the basket in 'Bracket & Basket Allocation' table.`;
  instructionsRange.setValue(instructionsText);

  // Set up Basket Stock Multiplier Tables
  let tableStartRow = instructionsRow + 2;
  let basketColStart = 1;
  for (let i = 0; i < data.baskets.length; i++) {
    let basketObj = data.baskets[i];
    let bName = basketObj.basket_name;
    let bId = basketObj.basket_id;

    let bracketTitleRange = sheet.getRange(tableStartRow, basketColStart, 1, 2);
    bracketTitleRange.merge();
    bracketTitleRange.setValue(bName);
    bracketTitleRange.setBackground("#BCD4FC");
    bracketTitleRange.setFontWeight("bold");
    bracketTitleRange.setHorizontalAlignment("center");

    // Put the basket_id in the second row, first column of this table
    let basketIdCell = sheet.getRange(tableStartRow - 1, basketColStart);
    basketIdCell.setValue(bId).setFontColor("#FFFFFF"); 

    let stockHeader = sheet.getRange(tableStartRow + 1, basketColStart);
    stockHeader.setValue("Stock")
      .setBackground("#91B9F9")
      .setFontWeight("bold")
      .setHorizontalAlignment("center");

    let multiplierHeader = sheet.getRange(tableStartRow + 1, basketColStart + 1);
    multiplierHeader.setValue("Multiplier")
      .setBackground("#91B9F9")
      .setFontWeight("bold")
      .setHorizontalAlignment("center");

    let mappingHeader = sheet.getRange(tableStartRow + 2, basketColStart + 2);
    mappingHeader.setFontColor("#FFFFFF"); // hide it entirely

    let stData = data.basket_stocks[bName] || [];
    let rowPos = tableStartRow + 2;
    for (let s = 0; s < stData.length; s++) {
      sheet.getRange(rowPos, basketColStart).setValue(stData[s].stock);
      sheet.getRange(rowPos, basketColStart + 1).setValue(stData[s].multiplier);
      sheet.getRange(rowPos, basketColStart + 2).setValue(stData[s].basket_stock_mapping_id).setFontColor("#FFFFFF");
      rowPos++;
    }
    basketColStart += 3;
  }
  sheet.activate();
}

function savePortfolioChanges() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getActiveSheet();
  const name = sheet.getName();
  if (!name.startsWith("Standard Portfolio")) {
    SpreadsheetApp.getUi().alert("Not the correct sheet.");
    return;
  }
  let dataPayload = buildPayloadFromSheet(sheet);

  /***************************************************************************************/
  // var sheet_1 = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Standard Portfolio");
  // var jsonString = JSON.stringify(dataPayload, null, 2);
  // sheet_1.getRange("A50").setValue(jsonString);
  /***************************************************************************************/

  // if (!validateMultiplierConstraints(dataPayload)) {
  //   SpreadsheetApp.getUi().alert("Sum of multipliers != number of stocks in a basket. Fix and retry.");
  //   return;
  // }
  let portfolioId = 1; 
  let url = "http://15.207.59.232:8000/portfolios/"+portfolioId+"/structure/save";
  let resp = UrlFetchApp.fetch(url, {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(dataPayload),
    muteHttpExceptions: true
  });
  if (resp.getResponseCode() == 200) {
    SpreadsheetApp.getUi().alert("Saved successfully!");
  } else {
    SpreadsheetApp.getUi().alert("Error saving: " + resp.getContentText());
  }
}

function buildPayloadFromSheet(sheet) {
  let brackets = [];
  let baskets = [];
  let allocations = {};
  let bracketStartRow = 5;
  let bracketColName = 1;
  let bracketColMin = 2;
  let bracketColMax = 3;
  let basketStartCol = 4;
  let row = bracketStartRow;

  // Extracting Brackets
  while (true) {
    let brName = String(sheet.getRange(row, bracketColName).getValue() || "").trim();
    let minVal = sheet.getRange(row, bracketColMin).getValue() || 0;
    let maxVal = sheet.getRange(row, bracketColMax).getValue() || 0;
    let bracketId = String(sheet.getRange(row, 50).getValue() || "").trim();
    
    if (!brName && minVal === 0 && maxVal === 0) break; // Stop when fully empty
    brackets.push({
      "bracket_id": bracketId ? bracketId.toString() : "",
      "bracket_name": brName,
      "min_amount": minVal,
      "max_amount": maxVal
      });
    row++;
    if (row > 200) break; // Prevent infinite loops
  }

  // Extract Baskets 
  let basketList = [];
  let col = basketStartCol;
  let firstRow = bracketStartRow - 1;
  let rowAllocStart = bracketStartRow;
  let bracketCount = brackets.length;

  while (col <= 50) {
    let bsName = String(sheet.getRange(firstRow, col).getValue() || "").trim();
    let basketId = String(sheet.getRange(1000, col).getValue() || "").trim();
    let hasNonZeroAllocation = false;
    // Check if any allocation in this column is non-zero
    for (let r = 0; r < bracketCount; r++) {
      let allocVal = sheet.getRange(rowAllocStart + r, col).getValue() || 0;
      if (allocVal !== 0) {
        hasNonZeroAllocation = true;
        break;
      }
    }
    // If the basket name is blank AND allocation is zero, skip this column.
    if (!hasNonZeroAllocation && bsName === "" && basketId === "" && bsName === "Total") {
      col++;
      continue;
    }
    if (bsName !== "" || basketId !== "") {
      basketList.push(bsName ? bsName : "");
      baskets.push({
        "basket_id": basketId,
        "basket_name": bsName,
        "allocation_method": "manual"
        });
    }
    col++;
  }

  // Extract Allocations (keyed by "bracket_id::basket_id")
  let basketCountFinal = baskets.length;
  for (let r = 0; r < bracketCount; r++) {
    let rowIdx = bracketStartRow + r;
    let brId = brackets[r].bracket_id;
    for (let c = 0; c < basketCountFinal; c++) {
      let colIdx = basketStartCol + c;
      let bsId = baskets[c].basket_id;
      let val = sheet.getRange(rowIdx, colIdx).getValue() || 0;
      allocations[brId + "::" + bsId] = val;
    }
  }

  // Extracting Basket Stocks
  let basketStocks = {};
  let stockTablesStart = bracketStartRow + bracketCount + 9;
  let colPos = 1;
  for (let i = 0; i < baskets.length; i++) {
    let bObj = baskets[i];
    let bId = bObj.basket_id; // This is the key
    let tableStartRow = stockTablesStart;
    
    let rowPtr = tableStartRow + 3;
    let stList = [];
    while(true) {
      let sName = String(sheet.getRange(rowPtr+2, colPos).getValue() || "").trim();
      let mult = sheet.getRange(rowPtr+2, colPos+1).getValue() || 0;
      let mappingId = sheet.getRange(rowPtr+2, colPos+2).getValue()
      if (!sName && mult == 0 && !mappingId) {
        break;
      }
      stList.push({
        "stock": sName ? sName : "",
        "multiplier": mult,
        "basket_stock_mapping_id": mappingId
      });
      rowPtr++;
      if (rowPtr > 500) break;
    }
    basketStocks[bId] = stList;
    colPos += 3;
  }
  return {
    brackets: brackets,
    baskets: baskets,
    allocations: allocations,
    basket_stocks: basketStocks
  };
}

function validateMultiplierConstraints(payload) {
  var sheet1 = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Standard Portfolio");
  sheet1.getRange("A50").setValue(JSON.stringify(payload, null, 2));
  let basket_stocks = payload.basket_stocks || {};
  for (let bName in basket_stocks) {
    let list = basket_stocks[bName];
    let countNonBlank = list.filter(x => x.stock && x.stock!="").length;
    let sumMult = list.reduce((acc,x)=>acc+(x.multiplier||0),0);
    if (Math.round(sumMult*100)/100 != countNonBlank) { 
      return false;
    }
  }
  return true;
}

function onEdit(e) {
  const sheet = e.range.getSheet();
  const editedCell = e.range;

  if (sheet.getName() !== "Standard Portfolio") return;

  let bracketStartRow = 5;
  let bracketColName = 1;
  let basketStartCol = 4;

  // Find the edited row and column
  let row = editedCell.getRow();
  let col = editedCell.getColumn();

  // Only trigger if within allocation range
  if (row < bracketStartRow || col < basketStartCol) return;

  // Calculate total for the edited bracket
  let total = 0;
  let lastCol = basketStartCol + sheet.getRange(bracketStartRow - 1, basketStartCol, 1, 50).getLastColumn();
  for (let c = basketStartCol; c < lastCol; c++) {
    let val = sheet.getRange(row, c).getValue() || 0;
    total += val;
  }

  // Update Total column
  let totalColIdx = lastCol + 1;
  let totalCell = sheet.getRange(row, totalColIdx);
  totalCell.setValue(total.toFixed(2));
  if (Math.abs(total - 100) < 0.01) {
    totalCell.setBackground("#C6EFCE");
  } else {
    totalCell.setBackground("#FFC7CE");
  }

  // Auto-correct if total > 100
  if (total > 100) {
    let excess = total - 100;

    // Find "Short Vol" column
    let shortVolCol = -1;
    for (let c = basketStartCol; c < lastCol; c++) {
      let basketName = (sheet.getRange(bracketStartRow - 1, c).getValue() || "").trim();
      if (basketName === "Short Vol") {
        shortVolCol = c;
        break;
      }
    }

    if (shortVolCol !== -1) {
      let currentShortVol = sheet.getRange(row, shortVolCol).getValue() || 0;
      let newShortVol = Math.max(0, currentShortVol - excess);
      sheet.getRange(row, shortVolCol).setValue(newShortVol);
    }

    // Recalculate Total after correction
    let correctedTotal = total - excess;
    totalCell.setValue(correctedTotal.toFixed(2));
    if (Math.abs(correctedTotal - 100) < 0.01) {
      totalCell.setBackground("#C6EFCE");
    } else {
      totalCell.setBackground("#FFC7CE");
    }
  }
}
