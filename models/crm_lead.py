from odoo import models, api


class CrmLead(models.Model):
    _inherit = "crm.lead"

    def action_download_all_attachments(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/binary/download_all_attachments/{self._name}/{self.id}",
            "target": "new",
        }
