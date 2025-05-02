# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class BookingMetrics(models.Model):
    _name = 'pitcar.booking.metrics'
    _description = 'Booking Metrics Summary'
    _order = 'date desc'
    
    date = fields.Date('Tanggal', required=True, index=True)
    period_type = fields.Selection([
        ('day', 'Harian'),
        ('week', 'Mingguan'),
        ('month', 'Bulanan')
    ], string='Periode', required=True, index=True)
    
    # Metrik jumlah booking berdasarkan status
    total_bookings = fields.Integer('Total Booking', required=True)
    draft_bookings = fields.Integer('Draft', required=True)
    confirmed_bookings = fields.Integer('Terkonfirmasi', required=True)
    converted_bookings = fields.Integer('Dikonversi ke SO', required=True)
    cancelled_bookings = fields.Integer('Dibatalkan', required=True)
    
    # Sub-metrik pembatalan berdasarkan alasan
    customer_cancelled = fields.Integer('Dibatalkan oleh Pelanggan')
    no_show_cancelled = fields.Integer('Pelanggan Tidak Hadir')
    rescheduled_cancelled = fields.Integer('Dijadwalkan Ulang')
    other_cancelled = fields.Integer('Dibatalkan: Alasan Lain')
    
    # Metrik persentase
    confirmation_rate = fields.Float('Tingkat Konfirmasi (%)', required=True)
    conversion_rate = fields.Float('Tingkat Konversi (%)', required=True)
    cancellation_rate = fields.Float('Tingkat Pembatalan (%)', required=True)
    
    # Metrik revenue
    potential_revenue = fields.Monetary('Potensi Pendapatan', currency_field='currency_id')
    actual_revenue = fields.Monetary('Pendapatan Aktual', currency_field='currency_id')
    lost_revenue = fields.Monetary('Pendapatan Hilang', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', readonly=True, default=lambda self: self.env.company.currency_id)
    
    # Metrik tambahan
    avg_service_duration = fields.Float('Rata-rata Durasi Layanan (jam)')
    avg_booking_value = fields.Monetary('Rata-rata Nilai Booking', currency_field='currency_id')

    @api.model
    def _cron_collect_daily_metrics(self):
        """Kumpulkan metrik booking harian"""
        yesterday = fields.Date.today() - timedelta(days=1)
        
        # Cek apakah sudah ada metrik untuk tanggal tersebut
        existing = self.env['pitcar.booking.metrics'].search([
            ('date', '=', yesterday),
            ('period_type', '=', 'day')
        ])
        
        if existing:
            return
        
        # Ambil semua booking untuk tanggal tersebut
        bookings = self.env['pitcar.service.booking'].search([
            ('booking_date', '=', yesterday)
        ])
        
        # Hitung metrik
        total = len(bookings)
        if total == 0:
            return
        
        # Hitung jumlah berdasarkan status
        draft = len(bookings.filtered(lambda b: b.state == 'draft'))
        confirmed = len(bookings.filtered(lambda b: b.state == 'confirmed'))
        converted = len(bookings.filtered(lambda b: b.state == 'converted'))
        cancelled = len(bookings.filtered(lambda b: b.state == 'cancelled'))
        
        # Breakdown pembatalan
        customer_cancelled = len(bookings.filtered(lambda b: b.state == 'cancelled' and b.cancellation_reason == 'customer'))
        no_show_cancelled = len(bookings.filtered(lambda b: b.state == 'cancelled' and b.cancellation_reason == 'no_show'))
        rescheduled_cancelled = len(bookings.filtered(lambda b: b.state == 'cancelled' and b.cancellation_reason == 'rescheduled'))
        other_cancelled = len(bookings.filtered(lambda b: b.state == 'cancelled' and b.cancellation_reason == 'other'))
        
        # Hitung persentase
        confirmation_rate = (confirmed + converted) / total * 100 if total > 0 else 0
        conversion_rate = converted / (confirmed + converted) * 100 if (confirmed + converted) > 0 else 0
        cancellation_rate = cancelled / total * 100 if total > 0 else 0
        
        # Hitung revenue
        potential_revenue = sum(bookings.mapped('amount_total'))
        actual_revenue = sum(bookings.filtered(lambda b: b.state == 'converted').mapped('amount_total'))
        lost_revenue = sum(bookings.filtered(lambda b: b.state == 'cancelled').mapped('amount_total'))
        
        # Hitung rata-rata
        avg_duration = sum(bookings.mapped('estimated_duration')) / total if total > 0 else 0
        avg_value = potential_revenue / total if total > 0 else 0
        
        # Buat record metrik
        metrics_vals = {
            'date': yesterday,
            'period_type': 'day',
            'total_bookings': total,
            'draft_bookings': draft,
            'confirmed_bookings': confirmed,
            'converted_bookings': converted,
            'cancelled_bookings': cancelled,
            'customer_cancelled': customer_cancelled,
            'no_show_cancelled': no_show_cancelled,
            'rescheduled_cancelled': rescheduled_cancelled,
            'other_cancelled': other_cancelled,
            'confirmation_rate': confirmation_rate,
            'conversion_rate': conversion_rate,
            'cancellation_rate': cancellation_rate,
            'potential_revenue': potential_revenue,
            'actual_revenue': actual_revenue,
            'lost_revenue': lost_revenue,
            'avg_service_duration': avg_duration,
            'avg_booking_value': avg_value,
        }
        
        # Buat record
        self.create(metrics_vals)

    @api.model
    def _get_action_domain(self):
        """Mendapatkan domain untuk action window"""
        today = fields.Date.context_today(self)
        first_day_of_month = today.replace(day=1)
        
        # Cari tanggal terakhir bulan ini (mengatasi issue bulan 28/30/31 hari)
        if today.month == 12:
            last_day_of_month = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day_of_month = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        
        return [
            ('date', '>=', first_day_of_month),
            ('date', '<=', last_day_of_month),
            ('period_type', '=', 'day')
        ]
    
    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        """Override search_read untuk menambahkan domain default"""
        if self.env.context.get('apply_default_domain', True):
            if domain is None:
                domain = []
            action_domain = self._get_action_domain()
            for item in action_domain:
                domain.append(item)
        return super(BookingMetrics, self).search_read(domain=domain, fields=fields, 
                                                    offset=offset, limit=limit, order=order)