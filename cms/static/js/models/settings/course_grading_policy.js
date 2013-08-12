define(["backbone", "js/models/location", "js/collections/course_grader"],
    function(Backbone, Location, CourseGraderCollection) {

var CourseGradingPolicy = Backbone.Model.extend({
    defaults : {
        course_location : null,
        graders : null,  // CourseGraderCollection
        grade_cutoffs : null,  // CourseGradeCutoff model
        grace_period : null // either null or { hours: n, minutes: m, ...}
    },
    parse: function(attributes) {
        if (attributes['course_location']) {
            attributes.course_location = new Location(attributes.course_location, {parse:true});
        }
        if (attributes['graders']) {
            var graderCollection;
            // interesting race condition: if {parse:true} when newing, then parse called before .attributes created
            if (this.attributes && this.has('graders')) {
                graderCollection = this.get('graders');
                graderCollection.reset(attributes.graders);
            }
            else {
                graderCollection = new CourseGraderCollection(attributes.graders);
                graderCollection.course_location = attributes['course_location'] || this.get('course_location');
            }
            attributes.graders = graderCollection;
        }
        return attributes;
    },
    url : function() {
        var location = this.get('course_location');
        return '/' + location.get('org') + "/" + location.get('course') + '/settings-details/' + location.get('name') + '/section/grading';
    },
    gracePeriodToDate : function() {
        var newDate = new Date();
        if (this.has('grace_period') && this.get('grace_period')['hours'])
            newDate.setHours(this.get('grace_period')['hours']);
        else newDate.setHours(0);
        if (this.has('grace_period') && this.get('grace_period')['minutes'])
            newDate.setMinutes(this.get('grace_period')['minutes']);
        else newDate.setMinutes(0);
        if (this.has('grace_period') && this.get('grace_period')['seconds'])
            newDate.setSeconds(this.get('grace_period')['seconds']);
        else newDate.setSeconds(0);

        return newDate;
    },
    dateToGracePeriod : function(date) {
        return {hours : date.getHours(), minutes : date.getMinutes(), seconds : date.getSeconds() };
    }
});

return CourseGradingPolicy;
}); // end define()
