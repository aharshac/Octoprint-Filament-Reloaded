$(function() {
	function J18FSPopUpViewModel(parameters) {
		var self = this;

		self.settingsViewModel = parameters[0];

		self.onBeforeBinding = function() {
			console.log('Binding J18FSPopUpViewModel')

			self.config = self.settingsViewModel.settings.plugins.Julia2018FilamentSensor;
			self.testStatus();
		}

		self.onDataUpdaterPluginMessage = function(plugin, data) {
			if (plugin != "Julia2018FilamentSensor") {
				// console.log('Ignoring '+plugin);
				return;
			}

			if (data.type != "popup")
				return;

			new PNotify({
				title: 'Julia 2018 Filament Sensor',
				text: data.msg,
				type: data.msgType,
				hide: (data && data.hasOwnProperty('hide') ? data.hide : true)
			});
		}

		self.testStatus = function(data) {
			var status = function(x) {
				switch (x) {
					case "-1":
						return "Sensor not used";
					case "0":
						return "No filament detected";
					case "1":
						return "Filament detected"
					default:
						return "Error"
				}
			};

			$.ajax("/plugin/Julia2018FilamentSensor/status")
			.success(function(data) {
				var filament = data.hasOwnProperty('filament') ? status(data['filament']) : status(-2);
				var filament2 = data.hasOwnProperty('filament2') ? status(data['filament2']) : status(-2);
				
				var msg = "<b>Filament 1:</b> " + filament + "\n<b>Filament 2:</b> " + filament2;
				self.onDataUpdaterPluginMessage("Julia2018FilamentSensor", {type: 'popup', msg, msgType:'info', hide:'false'});
			})
			.fail(function(req, status) {
				console.log(status)
				self.onDataUpdaterPluginMessage("Julia2018FilamentSensor", {msg: "Error", type:'info', hide:'false'});
			});
		}
	}


	// This is how our plugin registers itself with the application, by adding some configuration
	// information to the global variable OCTOPRINT_VIEWMODELS
	ADDITIONAL_VIEWMODELS.push([
		// This is the constructor to call for instantiating the plugin
		J18FSPopUpViewModel,

		// This is a list of dependencies to inject into the plugin, the order which you request
		// here is the order in which the dependencies will be injected into your view model upon
		// instantiation via the parameters argument
		["settingsViewModel"],

		// Finally, this is the list of selectors for all elements we want this view model to be bound to.
		["#settings_j18fs"]
	]);
});