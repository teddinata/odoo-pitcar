odoo.define('pitcar_custom.stall_dashboard', function (require) {
  "use strict";
  
  var core = require('web.core');
  var KanbanController = require('web.KanbanController');
  var KanbanRenderer = require('web.KanbanRenderer');
  var KanbanView = require('web.KanbanView');
  var viewRegistry = require('web.view_registry');
  var _t = core._t;
  
  // Monkey patch untuk mengatasi masalah evaluasi domain
  var ControlPanelModelExtension = require('web/static/src/js/views/control_panel/control_panel_model_extension.js');
  var originalGetDomain = ControlPanelModelExtension.prototype.getDomain;
  ControlPanelModelExtension.prototype.getDomain = function () {
      try {
          return originalGetDomain.apply(this, arguments);
      } catch (error) {
          console.warn("Error in domain evaluation:", error);
          return [];  // Return empty domain as fallback
      }
  };
  
  // Custom renderer untuk menampilkan semua stall meskipun kosong
  var StallKanbanRenderer = KanbanRenderer.extend({
      _renderGrouped: function (fragment) {
          var self = this;
          var result = this._super.apply(this, arguments);
          
          // Cek jika grouped by stall_id
          if (this.state.groupedBy[0] === 'stall_id') {
              // Logic untuk menampilkan semua stall meskipun kosong
              // (Ini memerlukan data dari model pitcar.service.stall)
              
              // Sort columns in visual order
              var columns = Array.from(fragment.querySelectorAll('.o_kanban_group'));
              columns.sort(function (a, b) {
                  var valueA = a.dataset.id || '';
                  var valueB = b.dataset.id || '';
                  
                  // Process stall name for comparison
                  var getStallNumber = function(value) {
                      if (!value) return 999; // Put empty at the end
                      var match = (value || "").match(/Stall (\d+)/i);
                      return match ? parseInt(match[1]) : 999;
                  };
                  
                  var numA = getStallNumber(valueA);
                  var numB = getStallNumber(valueB);
                  
                  return numA - numB;
              });
              
              // Clear the fragment and append columns in the sorted order
              while (fragment.firstChild) {
                  fragment.removeChild(fragment.firstChild);
              }
              
              columns.forEach(function (column) {
                  fragment.appendChild(column);
              });
          }
          
          return result;
      },
      
      _renderGroupHeader: function (group) {
          var result = this._super.apply(this, arguments);
          
          // You can enhance the group header if needed
          
          return result;
      }
  });
  
  var StallKanbanController = KanbanController.extend({
      _onMoveRecord: function (ev) {
          var self = this;
          this._super.apply(this, arguments);
          
          var recordID = ev.data.recordID;
          var groupID = ev.data.groupID;
          var record = this.model.get(recordID);
          var group = this.model.get(groupID);
          
          if (group && group.groupedBy && group.groupedBy[0] === 'stall_id') {
              var newStallId = group.res_id;
              
              // Update the record with new stall_id
              this._rpc({
                  model: 'pitcar.service.booking',
                  method: 'write',
                  args: [[record.res_id], {stall_id: newStallId || false}],
                  context: this.context,
              }).then(function() {
                  // Optional: Sync stall_position if needed
                  if (newStallId) {
                      self._rpc({
                          model: 'pitcar.service.stall',
                          method: 'read',
                          args: [newStallId, ['name']],
                          context: self.context,
                      }).then(function (stall) {
                          if (stall && stall.length && stall[0].name) {
                              var stallName = stall[0].name;
                              var match = stallName.match(/Stall (\d+)/i);
                              if (match && match[1]) {
                                  var stallNumber = parseInt(match[1]);
                                  if (stallNumber >= 1 && stallNumber <= 10) {
                                      self._rpc({
                                          model: 'pitcar.service.booking',
                                          method: 'write',
                                          args: [[record.res_id], {stall_position: 'stall' + stallNumber}],
                                          context: self.context,
                                      });
                                  }
                              }
                          }
                      });
                  } else {
                      // If moved to a "false" group (unassigned)
                      self._rpc({
                          model: 'pitcar.service.booking',
                          method: 'write',
                          args: [[record.res_id], {stall_position: 'unassigned'}],
                          context: self.context,
                      });
                  }
              });
          }
      }
  });
  
  var StallKanbanView = KanbanView.extend({
      config: _.extend({}, KanbanView.prototype.config, {
          Controller: StallKanbanController,
          Renderer: StallKanbanRenderer,
      }),
  });
  
  viewRegistry.add('stall_kanban', StallKanbanView);
  
  return {
      StallKanbanController: StallKanbanController,
      StallKanbanRenderer: StallKanbanRenderer,
      StallKanbanView: StallKanbanView,
  };
});