import base64
import io
import os
import tempfile
import zipfile

from odoo import http
from odoo.http import request, content_disposition


class DownloadAttachmentsController(http.Controller):
    @http.route(
        "/web/binary/download_all_attachments/<string:model>/<int:res_id>",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def download_all_attachments(self, model, res_id, **kwargs):
        try:
            Record = request.env[model]
            record = Record.browse(res_id)
            if not record.exists():
                return request.not_found()

            # Respect Odoo access rules
            record.check_access_rights("read")
            record.check_access_rule("read")

            attachments = request.env["ir.attachment"].search(
                [
                    ("res_model", "=", model),
                    ("res_id", "=", res_id),
                ]
            )

            if not attachments:
                # Return empty zip or a friendly message
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as _zf:
                    pass
                zip_buffer.seek(0)
                filename = f"{model.replace('.', '_')}_{res_id}_attachments.zip"
                return request.make_response(
                    zip_buffer.getvalue(),
                    headers=[
                        ("Content-Type", "application/zip"),
                        ("Content-Disposition", content_disposition(filename)),
                    ],
                )

            tempfile_path = None
            try:
                tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
                tempfile_path = tmp_file.name
                with zipfile.ZipFile(tmp_file, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for att in attachments:
                        if att.datas:
                            try:
                                file_data = base64.b64decode(att.datas)
                                name = att.name or f"attachment_{att.id}"
                                zip_file.writestr(name, file_data)
                            except Exception:
                                continue
                tmp_file.close()

                file_size = os.path.getsize(tempfile_path)
                filename = f"{model.replace('.', '_')}_{res_id}_attachments.zip"
                headers = [
                    ("Content-Type", "application/zip"),
                    ("Content-Disposition", content_disposition(filename)),
                    ("Content-Length", str(file_size)),
                    ("Content-Transfer-Encoding", "binary"),
                    ("X-Accel-Buffering", "no"),
                    ("Pragma", "public"),
                    ("Expires", "0"),
                    ("Cache-Control", "must-revalidate, post-check=0, pre-check=0"),
                ]

                def stream_file(file_path, chunk_size=1048576):
                    try:
                        with open(file_path, "rb") as chunk_file:
                            while True:
                                chunk = chunk_file.read(chunk_size)
                                if not chunk:
                                    break
                                yield chunk
                    finally:
                        try:
                            os.unlink(file_path)
                        except Exception:
                            pass

                return request.make_response(
                    stream_file(tempfile_path), headers=headers
                )
            except Exception:
                if tempfile_path and os.path.exists(tempfile_path):
                    try:
                        os.unlink(tempfile_path)
                    except Exception:
                        pass
                raise

        except Exception as e:
            # In production you might want better error handling / logging
            return request.make_response(f"Error generating ZIP: {str(e)}", status=500)
