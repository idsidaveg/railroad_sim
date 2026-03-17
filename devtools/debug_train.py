import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from debug_equipment import build_debug_equipment

from railroad_sim.domain.consist import Consist
from railroad_sim.domain.train import Train


def build_debug_train() -> Train:
    Consist._reset_registry_for_tests()
    """
    Build a mixed consist from the debug equipment set and wrap it in a Train.
    """
    equipment = build_debug_equipment()

    loco = equipment["loco"]
    boxcar = equipment["boxcar"]
    tankcar = equipment["tankcar"]
    intermodal = equipment["intermodal"]
    gondola = equipment["gondola"]
    caboose = equipment["caboose"]

    # LOCO -> BOXCAR -> TANKCAR -> INTERMODAL -> GONDOLA -> CABOOSE
    loco.rear_coupler.connect(boxcar.front_coupler)
    boxcar.rear_coupler.connect(tankcar.front_coupler)
    tankcar.rear_coupler.connect(intermodal.front_coupler)
    intermodal.rear_coupler.connect(gondola.front_coupler)
    gondola.rear_coupler.connect(caboose.front_coupler)

    consist = Consist(anchor=loco)

    train = Train(
        train_id="debug-train-001",
        symbol="DBG-01",
        current_consist=consist,
    )

    return train


def print_train_summary(train: Train) -> None:
    """
    Print a concise summary of the train and its ordered consist.
    """
    print("Train Summary")
    print("=" * 80)
    print(f"train_id         : {train.train_id}")
    print(f"symbol           : {train.symbol}")
    print(f"status           : {train.status.value}")

    consist = train.current_consist
    if consist is None:
        print("current_consist  : None")
        print("equipment count  : 0")
        return

    ordered = consist.ordered_equipment()

    print(f"current_consist  : {consist.consist_id}")
    print(f"equipment count  : {len(ordered)}")
    print()

    print("Ordered Equipment")
    print("=" * 80)

    for index, car in enumerate(ordered):
        print(f"[{index}] {car.equipment_id}")
        print(f"     class      : {car.equipment_class}")
        print(f"     asset_id   : {car.asset_id}")

        front_neighbor = (
            f"{car.front_coupler.connected_to.owner.equipment_id}:"
            f"{car.front_coupler.connected_to.position.name}"
            if car.front_coupler.connected_to is not None
            else "None"
        )

        rear_neighbor = (
            f"{car.rear_coupler.connected_to.owner.equipment_id}:"
            f"{car.rear_coupler.connected_to.position.name}"
            if car.rear_coupler.connected_to is not None
            else "None"
        )

        print(f"     front      : {front_neighbor}")
        print(f"     rear       : {rear_neighbor}")
        print()


if __name__ == "__main__":
    train = build_debug_train()
    print_train_summary(train)
