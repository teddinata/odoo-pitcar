# models/__init__.py - Correct loading order

# ============ CORE ODOO MODELS FIRST ============
from . import res_users  # Clean res_users dengan minimal LMS dependency
from . import res_partner_car
from . import pitcar_position
from . import res_partner
from . import stock_picking
from . import account_move
from . import sale_order
from . import sale_order_line
from . import product_product
from . import product_tag
from . import crm_tag
from . import service_advisor
from . import project_task
from . import feedback_classification
from . import product_template
from . import queue_management
from . import queue_metric
from . import quality_metrics
from . import service_advisor_kpi
from . import service_advisor_overview
from . import mechanic_kpi
from . import mechanic_overview_kpi
from . import hr_employee  # Original hr_employee
from . import hr_attendance
from . import work_location
from . import sale_order_template_line
from . import sop
from . import hr_employee_public
from . import service_booking
from . import hr_working_days_config
from . import kpi_detail
from . import lead_time_part
from . import frontoffice_equipment
from . import sale_order_part_item
from . import stock_mandatory_stockout
from . import stock_audit_report
from . import cs_chat_sampling
from . import cs_leads_verification
from . import cs_contact_monitoring
from . import cs_finance_check
from . import cs_leads
from . import cs_leads_analytics
from . import content_project
from . import mentor_request
from . import notification
from . import pitcar_tools
from . import mechanic_hand_tools
from . import project_management
from . import kaizen_training_program
from . import it_program
from . import team_project_notification
from . import team_project_automated_notification
from . import booking_metrics
from . import sale_order_template
from . import campaign_analytics

# ============ LOYALTY SYSTEM ============
from . import pitcar_loyalty_core
from . import pitcar_rewards
from . import pitcar_referral
from . import pitcar_loyalty_integration
from . import pitcar_loyalty_helpers
from . import sale_order_loyalty_integration
from . import video_management

# ============ LMS MODELS - LOAD AFTER CORE MODELS ============
# Load LMS core models first (independent)
from . import lms_core
from . import lms_assessment
from . import lms_competency
from . import lms_config

# Load LMS extensions AFTER core LMS models exist
from . import lms_hr_employee  # Safe extension of hr.employee dengan LMS fields

# COMMENT OUT yang bermasalah untuk sementara:
# from . import lms_existing_model_update  # Skip ini dulu sampai stable