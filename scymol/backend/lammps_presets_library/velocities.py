class StandardVelocitiesStage:
    def __init__(
        self,
        stage_instance,
        lammps_commands_instance,
        velocities_subset: str = "all",
        temp: float = 298.15,
        random_seed: int = 1234,
        dist_type: str = "gaussian",
        momentum: str = "yes",
        rotation: str = "no",
    ) -> None:
        """
        Initialize the StandardVelocitiesStage.

        Args:
            stage_instance: The instance of the stage.
            lammps_commands_instance: The instance of lammps_commands.
            velocities_subset (str, optional): Subset of atoms for which to initialize velocities. Default is 'all'.
            temp (float, optional): Temperature for velocity initialization. Default is 298.15.
            random_seed (int, optional): Random seed for velocity initialization. Default is 1234.
            dist_type (str, optional): Distribution type for initializing velocities. Default is 'gaussian'.
            momentum (str, optional): Initialize momentum (yes or no). Default is 'yes'.
            rotation (str, optional): Allow rotation (yes or no). Default is 'no'.
        """
        self.stage_instance = stage_instance
        self.lammps_commands_instance = lammps_commands_instance
        self.velocities_subset = velocities_subset
        self.temp = temp
        self.random_seed = random_seed
        self.dist_type = dist_type
        self.momentum = momentum
        self.rotation = rotation

    def run(self) -> None:
        """
        Run the standard velocities initialization stage.
        """
        title = "Velocities"
        numbering = (self.stage_instance.stage_nbr, self.stage_instance.substage_nbr)
        description = (
            f"Initialize velocities to {self.temp} (seed {self.random_seed}) "
            f"using a {self.dist_type} distribution."
        )

        self.lammps_commands_instance.add_substage_title(
            title=title, numbering=numbering, description=description
        )

        self.lammps_commands_instance.add_velocities(
            velocities_subset=self.velocities_subset,
            temp=self.temp,
            random_seed=self.random_seed,
            dist_type=self.dist_type,
            momentum=self.momentum,
            rotation=self.rotation,
        )
        self.stage_instance.substage_nbr += 1
