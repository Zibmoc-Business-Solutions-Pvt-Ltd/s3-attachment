import urllib.parse
import frappe
from frappe.core.doctype.file.file import File
from frappe_s3_attachment.controller import S3Operations

class CustomFile(File):
    def get_content(self, encodings=None) -> bytes | str:
        # If it's a folder, raise standard exception
        if self.is_folder:
            frappe.throw(frappe._("Cannot get file contents of a Folder"))

        # If doc has content already populated, return it directly
        if self.get("content"):
            self._content = self.content
            if self.decode:
                from frappe.core.doctype.file.utils import decode_file_content
                self._content = decode_file_content(self._content)
                self.decode = False
            return self._content

        # Determine if this file is stored on S3
        is_s3 = False
        key = None

        if self.file_url:
            if "frappe_s3_attachment.controller.generate_file" in self.file_url:
                is_s3 = True
                parsed = urllib.parse.urlparse(self.file_url)
                params = urllib.parse.parse_qs(parsed.query)
                if 'key' in params:
                    key = params['key'][0]
            else:
                try:
                    s3_settings = frappe.get_doc('S3 File Attachment', 'S3 File Attachment')
                    if s3_settings.bucket_name and s3_settings.bucket_name in self.file_url:
                        is_s3 = True
                except Exception:
                    pass

        # Fall back to content_hash if key wasn't extracted from the URL
        if is_s3 and not key:
            key = self.content_hash

        if is_s3 and key:
            try:
                s3_ops = S3Operations()
                response = s3_ops.read_file_from_s3(key)
                self._content = response['Body'].read()

                if encodings is None:
                    from frappe.core.doctype.file.file import FILE_ENCODING_OPTIONS
                    encodings = FILE_ENCODING_OPTIONS

                for encoding in encodings:
                    try:
                        self._content = self._content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue

                return self._content
            except Exception as e:
                frappe.log_error(f"Failed to fetch S3 file content: {str(e)}", "S3 Attachment Retrieval Error")
                frappe.throw(frappe._("Failed to fetch file content from S3: {0}").format(str(e)))

        return super().get_content(encodings=encodings)
