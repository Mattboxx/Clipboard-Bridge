# PDF Preview Dependencies

Windows PDF previews use [pypdfium2](https://github.com/pypdfium2-team/pypdfium2)
and PDFium. These components have their own licenses, independent of Clipboard
Bridge's MIT license. See the upstream [licensing information](https://pypdfium2.readthedocs.io/en/stable/readme.html#licensing).

Windows builds include the installed pypdfium2 distribution metadata and its
complete `licenses` directory, including notices for the bundled PDFium binary
and its dependencies. Build scripts explicitly collect this metadata. No Adobe
installation or separate PDF viewer is required to generate a thumbnail.
