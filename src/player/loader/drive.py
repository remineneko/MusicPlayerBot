import os
import re
import requests

from typing import List
from src.player.media_metadata import MediaMetadata
from .base import BaseLoader
from gdown.parse_url import parse_url
from gdown.download_folder import _parse_google_drive_file, _GoogleDriveFile


class GDriveLoader(BaseLoader):
    def load(self, url: str, **kwargs) -> List[MediaMetadata]:
        file_id, _ = parse_url(url)
        # we will try forcing the file_id first
        dl_url = "https://drive.google.com/uc?id={id}".format(id=file_id)
        file_name = self._get_file_name(dl_url)
        if file_name is None:
            # retrying with folder
            # canonicalize the language into English
            print("The provided Drive link is not a valid single file link. Retrying with folder.")
            sess = requests.session()

            sess.headers.update(
                {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_6)"}
            )

            all_files = self._get_children(url, sess)
            print(f"Found {len(all_files)} files")
            mm_data = []

            if not all_files:
                return mm_data
            
            for file in all_files:
                f_id = file.id
                f_name = file.name
                dl_url = "https://drive.google.com/uc?id={id}".format(id=f_id)
                fn, ext = os.path.splitext(f_name)
                ext = ext[1:]
                if ext not in MediaMetadata.SUPPORTED_FILE_TYPES:
                    pass
                else:
                    print(f"Obtaining metadata for {f_name}")
                    mm_data.append(MediaMetadata.from_title_extension(fn, ext, dl_url, id=f_id))
            
            return mm_data
                
        else:
            fn, ext = os.path.splitext(file_name)
            ext = ext[1:]
            if ext not in MediaMetadata.SUPPORTED_FILE_TYPES:
                # only media files are accept
                return []
            else:
                return MediaMetadata.from_title_extension(fn, ext, dl_url)

    def _get_file_name(self, dl_url: str) -> str | None:
        response = requests.get(dl_url)
        try:
            header = response.headers['Content-Disposition']
            file_name = re.search(r'filename\*=UTF-8''(.*)', header).group(1)
            return file_name[2:]
        except KeyError:
            return None
        
    def _get_children(self, folder_url, sess) -> List[_GoogleDriveFile]:
        if "?" in folder_url:
            folder_url += "&hl=en"
        else:
            folder_url += "?hl=en"

        res = sess.get(folder_url, verify=True)
        if res.status_code != 200:
            return []

        gdrive_file, id_name_type_iter = _parse_google_drive_file(
            url=folder_url,
            content=res.text,
        )

        for child_id, child_name, child_type in id_name_type_iter:
            if child_type != _GoogleDriveFile.TYPE_FOLDER:
                print(
                    "Processing file",
                    child_id,
                    child_name,
                )
                gdrive_file.children.append(
                    _GoogleDriveFile(
                        id=child_id,
                        name=child_name,
                        type=child_type,
                    )
                )
                continue
            
            print(
                "Retrieving folder",
                child_id,
                child_name,
            )
            child = self._get_children(
                folder_url="https://drive.google.com/drive/folders/" + child_id,
                sess=sess
            )
            gdrive_file.children.extend(child)

        return gdrive_file.children