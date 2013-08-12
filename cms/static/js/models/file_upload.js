define(["backbone"], function(Backbone) {
    var FileUpload = Backbone.Model.extend({
        defaults: {
            "title": "",
            "message": "",
            "selectedFile": null,
            "uploading": false,
            "uploadedBytes": 0,
            "totalBytes": 0,
            "finished": false
        },
        // NOTE: validation functions should return non-internationalized error
        // messages. The messages will be passed through gettext in the template.
        validate: function(attrs, options) {
            if(attrs.selectedFile && attrs.selectedFile.type !== "application/pdf") {
                return {
                    message: "Only PDF files can be uploaded. Please select a file ending in .pdf to upload.",
                    attributes: {selectedFile: true}
                };
            }
        }
    });
    return FileUpload;
});
