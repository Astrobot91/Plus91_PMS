import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import Dict, List, Any, Tuple
from datetime import datetime
from app.models.accounts import SingleAccount, JointAccount, JointAccountMapping
from app.models.clients import Broker, Client
from app.models.portfolio import (
    Basket, Bracket, PfBracketBasketAllocation,
    PortfolioTemplate
)
from app.models.accounts import AccountBracketBasketAllocation
from app.logger import logger, log_function_call


class AccountAllocationService:
    @staticmethod
    @log_function_call
    async def get_accounts_basket_allocations(db: AsyncSession) -> Dict[str, Any]:
        """Get basket allocation data for all accounts in a format suitable for Google Sheets."""
        try:
            logger.info("Starting to fetch basket allocation data for sheets")
            
            # Get all baskets for column headers - fetch once and store
            baskets_query = select(Basket).order_by(Basket.basket_id)
            logger.debug("Executing query to fetch baskets")
            baskets_result = await db.execute(baskets_query)
            baskets = baskets_result.scalars().all()
            baskets_list = list(baskets)  # Convert to list to reuse
            logger.info(f"Fetched {len(baskets_list)} baskets")
            
            # Get single accounts with their broker info
            logger.debug("Building single accounts query")
            single_accounts_query = (
                select(
                    SingleAccount,
                    Broker.broker_name,
                    Client.broker_code,
                    PortfolioTemplate.portfolio_name,
                    Bracket.bracket_name
                )
                .join(Client, SingleAccount.single_account_id == Client.account_id)
                .join(Broker, Client.broker_id == Broker.broker_id)
                .outerjoin(PortfolioTemplate, SingleAccount.portfolio_id == PortfolioTemplate.portfolio_id)
                .outerjoin(Bracket, SingleAccount.bracket_id == Bracket.bracket_id)
                .order_by(SingleAccount.single_account_id)
            )
            logger.debug("Executing single accounts query")
            single_results = await db.execute(single_accounts_query)
            
            # Get joint accounts with broker info through linked single accounts
            logger.debug("Building joint accounts query to get broker information")
            joint_broker_map_query = (
                select(
                    JointAccount.joint_account_id,
                    func.min(Broker.broker_name).label('primary_broker_name'),
                    func.string_agg(Client.broker_code, ' - ').label('broker_codes')
                )
                .join(
                    JointAccountMapping,
                    JointAccount.joint_account_id == JointAccountMapping.joint_account_id
                )
                .join(
                    SingleAccount,
                    JointAccountMapping.account_id == SingleAccount.single_account_id
                )
                .join(
                    Client,
                    SingleAccount.single_account_id == Client.account_id
                )
                .join(
                    Broker,
                    Client.broker_id == Broker.broker_id
                )
                .group_by(
                    JointAccount.joint_account_id
                )
            )
            joint_broker_result = await db.execute(joint_broker_map_query)
            joint_broker_map = {
                row[0]: (row[1], row[2]) for row in joint_broker_result
            }
            
            # Get joint accounts with portfolio and bracket info
            logger.debug("Building joint accounts query")
            joint_accounts_query = (
                select(
                    JointAccount,
                    PortfolioTemplate.portfolio_name,
                    Bracket.bracket_name
                )
                .outerjoin(PortfolioTemplate, JointAccount.portfolio_id == PortfolioTemplate.portfolio_id)
                .outerjoin(Bracket, JointAccount.bracket_id == Bracket.bracket_id)
                .order_by(JointAccount.joint_account_id)
            )
            logger.debug("Executing joint accounts query")
            joint_results = await db.execute(joint_accounts_query)

            # Get custom allocations with last updated timestamps
            logger.debug("Building custom allocations query")
            custom_allocs_query = select(
                AccountBracketBasketAllocation.owner_id, 
                AccountBracketBasketAllocation.owner_type,
                func.max(AccountBracketBasketAllocation.updated_at).label("max_updated")
            ).group_by(
                AccountBracketBasketAllocation.owner_id,
                AccountBracketBasketAllocation.owner_type
            )
            logger.debug("Executing custom allocations query")
            custom_allocs_dates = (await db.execute(custom_allocs_query)).all()
            
            # Create a map of last update dates - only from updated_at
            logger.debug("Creating update dates map")
            last_update_map = {
                (alloc[0], alloc[1]): alloc[2]
                for alloc in custom_allocs_dates
                if alloc[2] is not None  # Only include non-null values
            }
            
            # Get all allocations
            logger.debug("Building all allocations query")
            all_allocations_query = select(AccountBracketBasketAllocation)
            logger.debug("Executing all allocations query")
            all_allocations = (await db.execute(all_allocations_query)).scalars().all()
            
            logger.debug("Creating custom allocation map")
            custom_alloc_map = {
                (a.owner_id, a.owner_type, a.basket_id): (a.allocation_pct, a.is_custom)
                for a in all_allocations
            }

            # Get default allocations from portfolio template
            logger.debug("Building default allocations query")
            default_allocs_query = select(PfBracketBasketAllocation)
            logger.debug("Executing default allocations query")
            default_allocs = (await db.execute(default_allocs_query)).scalars().all()
            default_alloc_map = {
                (a.bracket_id, a.basket_id): a.allocation_pct
                for a in default_allocs
            }

            # Prepare sheet data
            logger.debug("Preparing sheet data")
            sheet_data = []

            # First row: Header with "Basket % Allocation"
            logger.debug("Creating header row")
            header_row = ["Basket % Allocation"] + [""] * 7 + [""] + [basket.basket_name for basket in baskets_list] + ["Updated At"]
            sheet_data.append(header_row)
            
            # Second row: Instructions
            logger.debug("Creating instruction row")
            instruction_row = ["Instructions: Check the 'Select' checkbox for accounts you want to update and modify the basket allocation percentages."] + [""] * (6 + len(baskets_list) + 1)
            sheet_data.append(instruction_row)
            
            # Third row: Column headers
            logger.debug("Creating column headers row")
            column_headers = [
                "Select", "Account ID", "Account Name", "Account Type", 
                "Broker Name", "Broker Code", "Portfolio Name",
                "Bracket Name", "Total % Allocation",
            ] + [basket.basket_name for basket in baskets_list] + ["Updated At"]
            sheet_data.append(column_headers)

            # Process single accounts
            logger.debug("Processing single accounts")
            single_results_list = list(single_results)
            logger.info(f"Found {len(single_results_list)} single accounts")
            
            for sa, broker_name, broker_code, pf_name, bracket_name in single_results_list:
                logger.debug(f"Processing single account {sa.single_account_id}")
                is_custom = False
                total_allocation = 0.0
                basket_allocations = []
                
                # Get allocation for each basket without re-fetching the baskets
                for basket in baskets_list:
                    custom_alloc = custom_alloc_map.get((sa.single_account_id, "single", basket.basket_id))
                    if custom_alloc:
                        allocation = custom_alloc[0]
                        is_custom = is_custom or custom_alloc[1]
                    else:
                        allocation = default_alloc_map.get((sa.bracket_id, basket.basket_id), 0.0) if sa.bracket_id else 0.0
                    
                    total_allocation += allocation
                    basket_allocations.append(allocation)
                
                # Get the last update date - use formatted string if available
                updated_at = last_update_map.get((sa.single_account_id, "single"), None)
                updated_at_str = updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else ""
                broker_name = broker_name or ""
                broker_code = broker_code or ""
                
                # Create the row
                row = [
                    False,
                    sa.single_account_id,
                    sa.account_name,
                    "single",
                    broker_name,
                    broker_code,
                    "Custom Portfolio" if is_custom else (pf_name or "Standard Portfolio"),
                    bracket_name or "",
                    total_allocation,
                ] + basket_allocations + [updated_at_str]
                
                sheet_data.append(row)

            # Process joint accounts
            logger.debug("Processing joint accounts")
            joint_results_list = list(joint_results)
            logger.info(f"Found {len(joint_results_list)} joint accounts")
            
            for ja, pf_name, bracket_name in joint_results_list:
                logger.debug(f"Processing joint account {ja.joint_account_id}")
                is_custom = False
                total_allocation = 0.0
                basket_allocations = []
                
                # Get broker info from our map
                broker_info = joint_broker_map.get(ja.joint_account_id, ("", ""))
                broker_name = broker_info[0] or ""
                broker_code = broker_info[1] or ""
                # Sort and format broker_code for joint accounts
                broker_codes_list = [code.strip() for code in broker_code.split(' - ') if code.strip()]
                broker_codes_list.sort()
                broker_code = " - ".join(broker_codes_list)
                
                # Get allocation for each basket without re-fetching the baskets
                for basket in baskets_list:
                    custom_alloc = custom_alloc_map.get((ja.joint_account_id, "joint", basket.basket_id))
                    if custom_alloc:
                        allocation = custom_alloc[0]
                        is_custom = is_custom or custom_alloc[1]
                    else:
                        allocation = default_alloc_map.get((ja.bracket_id, basket.basket_id), 0.0) if ja.bracket_id else 0.0
                    
                    total_allocation += allocation
                    basket_allocations.append(allocation)
                
                # Get the last update date
                updated_at = last_update_map.get((ja.joint_account_id, "joint"), None)
                updated_at_str = updated_at.strftime("%Y-%m-%d %H:%M") if updated_at else ""
                
                # Create the row
                row = [
                    False,
                    ja.joint_account_id,
                    ja.joint_account_name,
                    "joint",
                    broker_name,
                    broker_code,
                    "Custom Portfolio" if is_custom else (pf_name or "Standard Portfolio"),
                    bracket_name or "",
                    total_allocation,
                ] + basket_allocations + [updated_at_str]
                
                sheet_data.append(row)

            # Return data in the format expected by Google Sheets
            logger.info(f"Successfully built sheet data with {len(sheet_data) - 3} account rows")
            return {
                "data": sheet_data,
                "baskets": [{"id": b.basket_id, "name": b.basket_name, "is_leveraged": "(Leveraged)" in b.basket_name} for b in baskets_list]
            }
        except Exception as e:
            logger.error(f"Error in get_accounts_basket_allocations: {str(e)}", exc_info=True)
            raise

    @staticmethod
    @log_function_call
    async def update_account_allocations_from_sheet_json(
        db: AsyncSession, 
        json_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Update basket allocations from Google Sheets data in JSON object format.
        This method directly uses the new format with named properties.
        
        Special portfolio handling:
        - If account has is_custom=True and Portfolio Name is "Custom Portfolio" → Update with new custom allocations
        - If account has is_custom=True and Portfolio Name is "Standard Portfolio" → Reset to default allocations
        """
        results = []
        processed = 0
        errors = []
        
        try:
            # Get all baskets
            baskets_query = select(Basket).order_by(Basket.basket_id)
            baskets = (await db.execute(baskets_query)).scalars().all()
            basket_map = {b.basket_name: b.basket_id for b in baskets}
            
            # Log the data structure for debugging
            logger.info(f"JSON data objects: {len(json_data)}")
            if json_data:
                logger.info(f"Sample data fields: {list(json_data[0].keys())}")
            
            # Process each object in the data array
            for row_idx, row_obj in enumerate(json_data):
                logger.info(f"Processing row {row_idx}: {row_obj}")
                
                try:
                    # Extract account info directly from the object properties
                    account_id = row_obj.get("Account ID")
                    account_type = row_obj.get("Account Type", "").lower()
                    portfolio_name = row_obj.get("Portfolio Name", "")
                    
                    if not account_id or not account_type:
                        errors.append(f"Missing Account ID or Account Type in row {row_idx}")
                        continue
                    
                    # Check if this is a request to switch back to standard portfolio (case insensitive)
                    is_standard_portfolio_request = portfolio_name.lower() == "standard portfolio"
                    
                    # Get the account
                    if account_type == "single":
                        acc_query = select(SingleAccount).where(SingleAccount.single_account_id == account_id)
                        account = (await db.execute(acc_query)).scalar_one_or_none()
                    else:
                        acc_query = select(JointAccount).where(JointAccount.joint_account_id == account_id)
                        account = (await db.execute(acc_query)).scalar_one_or_none()
                    
                    if not account:
                        errors.append(f"Account not found: {account_id} (type: {account_type})")
                        continue
                    
                    # Check if account currently has custom allocations
                    alloc_query = select(AccountBracketBasketAllocation).where(
                        and_(
                            AccountBracketBasketAllocation.owner_id == account_id,
                            AccountBracketBasketAllocation.owner_type == account_type,
                            AccountBracketBasketAllocation.is_custom == True
                        )
                    )
                    custom_allocations = (await db.execute(alloc_query)).scalars().all()
                    has_custom_allocations = len(custom_allocations) > 0
                    
                    # If account has custom allocations but standard portfolio is requested,
                    # reset to default allocations
                    if has_custom_allocations and is_standard_portfolio_request:
                        logger.info(f"Reverting account {account_id} from custom to standard portfolio")
                        
                        # Get the account's bracket for default allocations
                        bracket_id = account.bracket_id
                        if not bracket_id:
                            errors.append(f"Account has no bracket_id: {account_id}")
                            continue
                        
                        # Get default allocations for this bracket
                        default_allocs_query = select(PfBracketBasketAllocation).where(
                            PfBracketBasketAllocation.bracket_id == bracket_id
                        )
                        default_allocs = (await db.execute(default_allocs_query)).scalars().all()
                        default_map = {a.basket_id: a.allocation_pct for a in default_allocs}
                        
                        # Reset all allocations to default values and mark as not custom
                        for alloc in custom_allocations:
                            alloc.allocation_pct = default_map.get(alloc.basket_id, 0.0)
                            alloc.is_custom = False
                            alloc.updated_at = datetime.now()
                        
                        # Set account portfolio to standard
                        account.portfolio_id = 1
                        
                        processed += 1
                        results.append({
                            "account_id": account_id,
                            "status": "success",
                            "message": "Reverted to standard portfolio allocations"
                        })
                        
                    # For all other cases, use the existing logic to process allocations
                    else:
                        # Get basket allocations from the JSON object
                        basket_allocations = {}
                        
                        # Process each basket using the basket name as the key
                        for basket in baskets:
                            if basket.basket_name in row_obj:
                                try:
                                    # Handle different value formats
                                    value = row_obj[basket.basket_name]
                                    
                                    # Convert percent string to number if needed
                                    if isinstance(value, str):
                                        # Remove % sign if present
                                        value = value.replace('%', '').strip()
                                        value = float(value) if value else 0.0
                                    
                                    # Ensure value is a float
                                    allocation = float(value)
                                    basket_allocations[basket.basket_name] = allocation
                                    logger.info(f"Basket {basket.basket_name} allocation: {allocation}")
                                except (ValueError, TypeError) as e:
                                    errors.append(f"Invalid allocation value for {account_id}, basket {basket.basket_name}: {row_obj[basket.basket_name]}")
                                    logger.warning(f"Error parsing allocation: {str(e)}")
                        
                        # Create update dictionary
                        update = {
                            "account_id": account_id,
                            "account_type": account_type,
                            **basket_allocations
                        }
                        
                        # Update allocations using the existing method
                        logger.info(f"Updating allocations for {account_id}: {basket_allocations}")
                        await AccountAllocationService.update_account_allocations(db, [update])
                        processed += 1
                        results.append({
                            "account_id": account_id,
                            "status": "success",
                            "message": f"Updated {len(basket_allocations)} basket allocations"
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing row {row_idx}: {str(e)}", exc_info=True)
                    errors.append(f"Error for account {row_obj.get('Account ID', 'unknown')}: {str(e)}")
            
            await db.commit()
            
        except Exception as e:
            logger.error(f"Error in update_account_allocations_from_sheet_json: {str(e)}", exc_info=True)
            errors.append(f"General error: {str(e)}")
            await db.rollback()
        
        return {
            "total_rows": len(json_data),
            "processed": processed,
            "results": results,
            "errors": errors
        }

    @staticmethod
    @log_function_call
    async def update_account_allocations(
        db: AsyncSession, 
        account_updates: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update basket allocations for the given accounts."""
        results = []
        processed = 0

        # Get all baskets
        baskets_query = select(Basket)
        baskets = (await db.execute(baskets_query)).scalars().all()
        basket_map = {b.basket_name: b.basket_id for b in baskets}

        # Get or create a special portfolio entry for custom allocations (ID=0)
        custom_portfolio_query = select(PortfolioTemplate).where(
            PortfolioTemplate.portfolio_id == 0
        )
        custom_portfolio = (await db.execute(custom_portfolio_query)).scalar_one_or_none()
        
        # Get standard portfolio (ID=1)
        std_portfolio_query = select(PortfolioTemplate).where(
            PortfolioTemplate.portfolio_id == 1
        )
        std_portfolio = (await db.execute(std_portfolio_query)).scalar_one_or_none()
        
        if not std_portfolio:
            logger.error("Standard Portfolio (ID=1) not found in the database!")
            raise ValueError("Standard Portfolio (ID=1) not found in the database")
            
        # If custom portfolio doesn't exist, create it with ID=0 using SQLAlchemy ORM
        if not custom_portfolio:
            logger.info("Creating Custom Portfolio template with ID=0")
            try:
                # First check if we need to modify the sequence to allow setting manual IDs
                from sqlalchemy import MetaData, Table
                from sqlalchemy.sql import text
                
                metadata = MetaData()
                # Use regular insert to bypass SQLAlchemy's ORM
                await db.execute(
                    text("""
                    INSERT INTO portfolio_template_details(portfolio_id, portfolio_name, description)
                    VALUES(0, 'Custom Portfolio', 'Custom allocations defined at account level')
                    """)
                )
                
                # Get the sequence name for reset
                await db.execute(
                    text("""
                    SELECT setval(pg_get_serial_sequence('portfolio_template_details', 'portfolio_id'), 
                           (SELECT MAX(portfolio_id) FROM portfolio_template_details), true)
                    """)
                )
                
                await db.commit()
                
                # Refresh our reference to the custom portfolio
                custom_portfolio_query = select(PortfolioTemplate).where(
                    PortfolioTemplate.portfolio_id == 0
                )
                custom_portfolio = (await db.execute(custom_portfolio_query)).scalar_one_or_none()
                logger.info("Created Custom Portfolio template with ID=0")
            except Exception as e:
                logger.error(f"Error creating custom portfolio template: {str(e)}", exc_info=True)
                # Use a different approach if the first method fails
                try:
                    # Alternative approach - create a dummy first and then update its ID
                    custom_portfolio = PortfolioTemplate(
                        portfolio_name="Custom Portfolio",
                        description="Custom allocations defined at account level"
                    )
                    db.add(custom_portfolio)
                    await db.flush()  # Generate an ID
                    
                    # Now update the ID to 0 using a direct update
                    await db.execute(
                        text("""
                        UPDATE portfolio_template_details 
                        SET portfolio_id = 0 
                        WHERE portfolio_id = :old_id
                        """),
                        {"old_id": custom_portfolio.portfolio_id}
                    )
                    await db.commit()
                    logger.info("Created Custom Portfolio template with ID=0 (alternative method)")
                except Exception as inner_e:
                    logger.error(f"Error creating custom portfolio (alternative method): {str(inner_e)}", exc_info=True)
                    await db.rollback()
                    # Continue processing other updates even if we can't create custom portfolio

        # Process each account update
        for update in account_updates:
            account_id = update.get("account_id")
            account_type = update.get("account_type")
            if not account_id or not account_type:
                logger.warning(f"Skipping update with missing account_id or account_type: {update}")
                continue

            try:
                # Get default allocations for comparison
                if account_type == "single":
                    acc_query = select(SingleAccount).where(SingleAccount.single_account_id == account_id)
                else:
                    acc_query = select(JointAccount).where(JointAccount.joint_account_id == account_id)
                
                account = (await db.execute(acc_query)).scalar_one_or_none()
                if not account:
                    logger.warning(f"Account not found: {account_id} (type: {account_type})")
                    continue

                bracket_id = account.bracket_id
                if not bracket_id:
                    logger.warning(f"Account has no bracket_id: {account_id} (type: {account_type})")
                    continue

                default_allocs_query = select(PfBracketBasketAllocation).where(
                    PfBracketBasketAllocation.bracket_id == bracket_id
                )
                default_allocs = (await db.execute(default_allocs_query)).scalars().all()
                default_map = {
                    (a.bracket_id, a.basket_id): a.allocation_pct
                    for a in default_allocs
                }

                # Check each basket allocation
                is_custom = False
                for basket_name, new_alloc in update.items():
                    if basket_name in ["account_id", "account_type"]:
                        continue
                        
                    basket_id = basket_map.get(basket_name)
                    if not basket_id:
                        logger.warning(f"Basket not found: {basket_name}")
                        continue

                    default_alloc = default_map.get((bracket_id, basket_id), 0.0)
                    if abs(float(new_alloc) - default_alloc) > 0.01:  # Allow small floating point differences
                        is_custom = True
                        break

                # Update portfolio_id based on whether allocations are custom
                if is_custom:
                    account.portfolio_id = 0  # Use 0 for custom portfolio as originally intended
                else:
                    account.portfolio_id = 1  # Standard portfolio ID
                
                # Update or create allocations
                for basket_name, new_alloc in update.items():
                    if basket_name in ["account_id", "account_type"]:
                        continue
                        
                    basket_id = basket_map.get(basket_name)
                    if not basket_id:
                        continue

                    # Find existing allocation
                    alloc_query = select(AccountBracketBasketAllocation).where(
                        and_(
                            AccountBracketBasketAllocation.owner_id == account_id,
                            AccountBracketBasketAllocation.owner_type == account_type,
                            AccountBracketBasketAllocation.basket_id == basket_id
                        )
                    )
                    existing_alloc = (await db.execute(alloc_query)).scalar_one_or_none()

                    current_time = datetime.now()

                    if existing_alloc:
                        existing_alloc.allocation_pct = float(new_alloc)
                        existing_alloc.is_custom = is_custom
                        existing_alloc.updated_at = current_time
                    else:
                        new_alloc_obj = AccountBracketBasketAllocation(
                            owner_id=account_id,
                            owner_type=account_type,
                            bracket_id=bracket_id,
                            basket_id=basket_id,
                            allocation_pct=float(new_alloc),
                            is_custom=is_custom,
                            created_at=current_time,
                            updated_at=current_time
                        )
                        db.add(new_alloc_obj)

                processed += 1
                results.append({
                    "account_id": account_id,
                    "status": "success",
                    "is_custom": is_custom
                })
                
            except Exception as e:
                logger.error(f"Error processing update for account {account_id}: {str(e)}", exc_info=True)
                results.append({
                    "account_id": account_id,
                    "status": "error",
                    "message": str(e)
                })

        await db.commit()

        return {
            "total_accounts": len(account_updates),
            "processed": processed,
            "results": results
        }
    
