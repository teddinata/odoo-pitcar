# models/lms_assessment.py  
from odoo import models, fields, api, _
from datetime import datetime, timedelta
import json
import logging

_logger = logging.getLogger(__name__)

class LMSAssessment(models.Model):
    """Master data untuk assessment/quiz"""
    _name = 'lms.assessment'
    _description = 'LMS Assessment'
    _order = 'name'
    
    name = fields.Char('Assessment Name', required=True, translate=True)
    module_id = fields.Many2one('lms.module', string='Module', ondelete='cascade')
    course_id = fields.Many2one('lms.course', related='module_id.course_id', store=True)
    
    # Assessment Type
    assessment_type = fields.Selection([
        ('pre_test', 'Pre-test'),
        ('post_test', 'Post-test'), 
        ('quiz', 'Quiz'),
        ('final_exam', 'Final Exam'),
        ('practice', 'Practice Test')
    ], string='Assessment Type', required=True, default='quiz')
    
    description = fields.Html('Description', translate=True)
    instructions = fields.Html('Instructions', translate=True)
    
    # Assessment Settings
    passing_score = fields.Float('Passing Score (%)', default=70.0, required=True)
    max_attempts = fields.Integer('Maximum Attempts', default=3)
    time_limit_minutes = fields.Integer('Time Limit (Minutes)', default=0,
                                       help='0 means no time limit')
    shuffle_questions = fields.Boolean('Shuffle Questions', default=True)
    show_correct_answers = fields.Boolean('Show Correct Answers After Completion', default=True)
    
    # Questions
    question_ids = fields.One2many('lms.question', 'assessment_id', string='Questions')
    question_count = fields.Integer('Question Count', compute='_compute_question_count')
    total_points = fields.Float('Total Points', compute='_compute_total_points')
    
    # Status
    active = fields.Boolean('Active', default=True)
    is_published = fields.Boolean('Published', default=False)
    
    # Results
    result_ids = fields.One2many('lms.result', 'assessment_id', string='Results')
    attempt_count = fields.Integer('Total Attempts', compute='_compute_attempt_stats')
    average_score = fields.Float('Average Score', compute='_compute_attempt_stats')
    pass_rate = fields.Float('Pass Rate (%)', compute='_compute_attempt_stats')
    
    @api.depends('question_ids')
    def _compute_question_count(self):
        for assessment in self:
            assessment.question_count = len(assessment.question_ids)
    
    @api.depends('question_ids.points')
    def _compute_total_points(self):
        for assessment in self:
            assessment.total_points = sum(assessment.question_ids.mapped('points'))
    
    @api.depends('result_ids', 'result_ids.score_percentage', 'result_ids.passed')
    def _compute_attempt_stats(self):
        for assessment in self:
            results = assessment.result_ids
            assessment.attempt_count = len(results)
            
            if results:
                assessment.average_score = sum(results.mapped('score_percentage')) / len(results)
                passed_results = results.filtered('passed')
                assessment.pass_rate = (len(passed_results) / len(results)) * 100
            else:
                assessment.average_score = 0
                assessment.pass_rate = 0

    def action_view_assessment_questions(self):
        """View questions for this assessment"""
        self.ensure_one()
        return {
            'name': f'Questions - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'lms.question',
            'view_mode': 'tree,form',
            'domain': [('assessment_id', '=', self.id)],
            'context': {'default_assessment_id': self.id}
        }
    
    def action_view_assessment_results(self):
        """View results for this assessment"""
        self.ensure_one()
        return {
            'name': f'Results - {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'lms.result',
            'view_mode': 'tree,form',
            'domain': [('assessment_id', '=', self.id)],
            'context': {'default_assessment_id': self.id}
        }


class LMSQuestion(models.Model):
    """Bank soal untuk assessment"""
    _name = 'lms.question'
    _description = 'LMS Question'
    _order = 'sequence, id'
    
    assessment_id = fields.Many2one('lms.assessment', string='Assessment', ondelete='cascade')
    course_id = fields.Many2one('lms.course', related='assessment_id.course_id', store=True)
    
    # Question Content
    question_text = fields.Html('Question', required=True, translate=True)
    question_type = fields.Selection([
        ('multiple_choice', 'Multiple Choice'),
        ('true_false', 'True/False'),
        ('essay', 'Essay'), 
        ('fill_blank', 'Fill in the Blank'),
        ('practical', 'Practical/Simulation')
    ], string='Question Type', required=True, default='multiple_choice')
    
    # Question Properties
    sequence = fields.Integer('Sequence', default=10)
    points = fields.Float('Points', default=1.0, required=True)
    difficulty = fields.Selection([
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard')
    ], string='Difficulty', default='medium')
    
    # Answer Options (for multiple choice, true/false)
    option_ids = fields.One2many('lms.question.option', 'question_id', string='Answer Options')
    
    # Correct Answer (stored as JSON for flexibility)
    correct_answer = fields.Text('Correct Answer',
                                help='Correct answer stored as JSON for different question types')
    explanation = fields.Html('Answer Explanation', translate=True)
    
    # Media
    image = fields.Binary('Question Image', attachment=True)
    image_filename = fields.Char('Image Filename')
    
    # Stats
    answer_count = fields.Integer('Answer Count', compute='_compute_answer_stats')
    correct_rate = fields.Float('Correct Rate (%)', compute='_compute_answer_stats')
    
    active = fields.Boolean('Active', default=True)
    
    @api.depends('assessment_id.result_ids')
    def _compute_answer_stats(self):
        for question in self:
            # This would need to be implemented based on result details
            # For now, set defaults
            question.answer_count = 0
            question.correct_rate = 0.0
    
    @api.model
    def create(self, vals):
        """Auto-create options for true/false questions"""
        question = super().create(vals)
        if question.question_type == 'true_false' and not question.option_ids:
            # Create True/False options
            self.env['lms.question.option'].create([
                {
                    'question_id': question.id,
                    'option_text': 'True',
                    'sequence': 1
                },
                {
                    'question_id': question.id, 
                    'option_text': 'False',
                    'sequence': 2
                }
            ])
        return question


class LMSQuestionOption(models.Model):
    """Pilihan jawaban untuk soal multiple choice"""
    _name = 'lms.question.option'
    _description = 'LMS Question Option'
    _order = 'sequence'
    
    question_id = fields.Many2one('lms.question', string='Question', 
                                 required=True, ondelete='cascade')
    option_text = fields.Html('Option Text', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=10)
    is_correct = fields.Boolean('Is Correct Answer', default=False)
    
    # Optional image for option
    image = fields.Binary('Option Image', attachment=True)
    image_filename = fields.Char('Image Filename')


class LMSResult(models.Model):
    """Hasil assessment per user per attempt"""
    _name = 'lms.result'
    _description = 'LMS Assessment Result'
    _rec_name = 'display_name'
    _order = 'create_date desc'
    
    # Relations
    user_id = fields.Many2one('res.users', string='User', required=True)
    employee_id = fields.Many2one('hr.employee', related='user_id.employee_id', store=True)
    assessment_id = fields.Many2one('lms.assessment', string='Assessment', 
                                   required=True, ondelete='cascade')
    progress_id = fields.Many2one('lms.progress', string='Module Progress')
    enrollment_id = fields.Many2one('lms.enrollment', related='progress_id.enrollment_id', store=True)
    
    # Attempt Info
    attempt_number = fields.Integer('Attempt Number', required=True)
    start_time = fields.Datetime('Start Time', required=True, default=fields.Datetime.now)
    end_time = fields.Datetime('End Time')
    duration_minutes = fields.Integer('Duration (Minutes)', compute='_compute_duration')
    
    # Scoring
    total_questions = fields.Integer('Total Questions')
    correct_answers = fields.Integer('Correct Answers', default=0)
    score_points = fields.Float('Score (Points)', default=0.0)
    score_percentage = fields.Float('Score (%)', compute='_compute_score_percentage', store=True)
    passed = fields.Boolean('Passed', compute='_compute_passed', store=True)
    
    # Status
    status = fields.Selection([
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('timeout', 'Timeout'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='in_progress')
    
    # Answer Details (stored as JSON)
    answer_details = fields.Text('Answer Details', 
                                help='JSON containing detailed answers for each question')
    
    # Gamification
    points_earned = fields.Integer('Points Earned', default=0)
    
    # Auto-computed fields
    display_name = fields.Char('Display Name', compute='_compute_display_name')
    
    @api.depends('user_id', 'assessment_id', 'attempt_number')
    def _compute_display_name(self):
        for result in self:
            result.display_name = f"{result.user_id.name} - {result.assessment_id.name} (Attempt {result.attempt_number})"
    
    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for result in self:
            if result.start_time and result.end_time:
                delta = result.end_time - result.start_time
                result.duration_minutes = int(delta.total_seconds() / 60)
            else:
                result.duration_minutes = 0
    
    @api.depends('score_points', 'assessment_id.total_points')
    def _compute_score_percentage(self):
        for result in self:
            if result.assessment_id.total_points > 0:
                result.score_percentage = (result.score_points / result.assessment_id.total_points) * 100
            else:
                result.score_percentage = 0
    
    @api.depends('score_percentage', 'assessment_id.passing_score')
    def _compute_passed(self):
        for result in self:
            result.passed = result.score_percentage >= result.assessment_id.passing_score
    
    def action_submit_assessment(self, answers):
        """Submit assessment and calculate score"""
        self.ensure_one()
        
        if self.status != 'in_progress':
            raise ValueError("Assessment is not in progress")
        
        self.end_time = fields.Datetime.now()
        self.status = 'completed'
        
        # Store answers
        self.answer_details = json.dumps(answers)
        
        # Calculate score
        self._calculate_score(answers)
        
        # Update related progress
        if self.progress_id:
            self.progress_id.attempts += 1
            if self.passed:
                self.progress_id.best_score = max(self.progress_id.best_score, self.score_percentage)
                self.progress_id.action_mark_completed()
            self.progress_id.last_score = self.score_percentage
        
        # Award points for passing
        if self.passed and not self.points_earned:
            self.points_earned = int(self.score_percentage / 10)  # 1 point per 10%
            self.user_id.karma += self.points_earned
        
        return self.score_percentage
    
    def _calculate_score(self, answers):
        """Calculate score based on answers"""
        total_points = 0
        correct_count = 0
        
        for question in self.assessment_id.question_ids:
            question_id = str(question.id)
            if question_id in answers:
                user_answer = answers[question_id]
                
                # Check if answer is correct based on question type
                if self._is_answer_correct(question, user_answer):
                    total_points += question.points
                    correct_count += 1
        
        self.score_points = total_points
        self.correct_answers = correct_count
        self.total_questions = len(self.assessment_id.question_ids)
    
    def _is_answer_correct(self, question, user_answer):
        """Check if user answer is correct for given question"""
        if question.question_type in ['multiple_choice', 'true_false']:
            # For MC and T/F, check against correct option
            correct_options = question.option_ids.filtered('is_correct')
            if correct_options:
                return str(correct_options[0].id) == str(user_answer)
        
        elif question.question_type == 'fill_blank':
            # For fill in blank, compare text (case insensitive)
            correct_answer = json.loads(question.correct_answer or '{}')
            expected = correct_answer.get('text', '').lower().strip()
            return expected == str(user_answer).lower().strip()
        
        # For essay and practical, manual grading needed
        return False
    
    def action_review_answers(self):
        """Open detailed answer review"""
        return {
            'name': 'Review Answers',
            'type': 'ir.actions.act_window',
            'res_model': 'lms.result.review.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_result_id': self.id}
        }


class LMSResultDetail(models.Model):
    """Detail jawaban per soal per attempt"""
    _name = 'lms.result.detail'
    _description = 'LMS Result Detail'
    
    result_id = fields.Many2one('lms.result', string='Result', required=True, ondelete='cascade')
    question_id = fields.Many2one('lms.question', string='Question', required=True)
    
    # User Answer
    user_answer = fields.Text('User Answer')
    selected_option_id = fields.Many2one('lms.question.option', string='Selected Option')
    
    # Scoring
    is_correct = fields.Boolean('Is Correct', default=False)
    points_earned = fields.Float('Points Earned', default=0.0)
    points_possible = fields.Float('Points Possible', related='question_id.points')
    
    # Timestamps
    answered_at = fields.Datetime('Answered At')
    time_spent_seconds = fields.Integer('Time Spent (Seconds)', default=0)